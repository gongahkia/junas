#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

export KAYPOH_FAIL_ON_LAYER_LOAD_ERROR="${KAYPOH_FAIL_ON_LAYER_LOAD_ERROR:-1}"

CANONICAL_LAYERS=("lexicon" "embedding" "clustering" "model1" "model2" "mosaic" "regression")
PIPELINE_LAYERS_NORMALIZED=""

trap cleanup_services EXIT INT TERM

echo "🚀 Starting Kaypoh development services..."

apply_pipeline_selection() {
    local requested
    local normalized
    local raw_layer
    local allowed_layer
    local unknown=()
    local ordered=()
    local seen=","

    requested="$1"
    normalized="$(printf '%s' "${requested}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"

    if [ -z "${normalized}" ]; then
        return 1
    fi

    IFS=',' read -r -a raw_layers <<< "${normalized}"

    for raw_layer in "${raw_layers[@]}"; do
        if [ -z "${raw_layer}" ]; then
            continue
        fi

        local found=0
        for allowed_layer in "${CANONICAL_LAYERS[@]}"; do
            if [ "${raw_layer}" = "${allowed_layer}" ]; then
                found=1
                break
            fi
        done

        if [ "${found}" -ne 1 ]; then
            unknown+=("${raw_layer}")
        fi
    done

    if [ "${#unknown[@]}" -gt 0 ]; then
        echo "⚠️  Unknown layer(s): ${unknown[*]}"
        echo "    Valid layers: ${CANONICAL_LAYERS[*]}"
        return 1
    fi

    for allowed_layer in "${CANONICAL_LAYERS[@]}"; do
        case ",${normalized}," in
            *,"${allowed_layer}",*)
                case "${seen}" in
                    *,"${allowed_layer}",*) ;;
                    *)
                        ordered+=("${allowed_layer}")
                        seen="${seen}${allowed_layer},"
                        ;;
                esac
                ;;
        esac
    done

    if [ "${#ordered[@]}" -eq 0 ]; then
        return 1
    fi

    PIPELINE_LAYERS_NORMALIZED="$(IFS=','; echo "${ordered[*]}")"
    export PIPELINE_LAYERS="${PIPELINE_LAYERS_NORMALIZED}"
    return 0
}

print_pipeline_notes() {
    case ",${PIPELINE_LAYERS_NORMALIZED}," in
        *,clustering,*)
            case ",${PIPELINE_LAYERS_NORMALIZED}," in
                *,embedding,*) ;;
                *)
                    echo "⚠️  Clustering without embedding will be configured but skipped at runtime."
                    ;;
            esac
            ;;
    esac

    case ",${PIPELINE_LAYERS_NORMALIZED}," in
        *,model2,*)
            case ",${PIPELINE_LAYERS_NORMALIZED}," in
                *,model1,*) ;;
                *)
                    echo "⚠️  Model 2 without Model 1 will usually remain skipped because Model 1 gates it."
                    ;;
            esac
            ;;
    esac

    case ",${PIPELINE_LAYERS_NORMALIZED}," in
        *,mosaic,*)
            case ",${PIPELINE_LAYERS_NORMALIZED}," in
                *,model1,*|*,model2,*) ;;
                *)
                    echo "⚠️  Mosaic is most useful when upstream classifiers are also selected."
                    ;;
            esac
            ;;
    esac
}

prompt_pipeline_layers() {
    if [ -n "${PIPELINE_LAYERS:-}" ]; then
        if ! apply_pipeline_selection "${PIPELINE_LAYERS}"; then
            echo "❌ Invalid PIPELINE_LAYERS value: ${PIPELINE_LAYERS}"
            exit 1
        fi
        return
    fi

    if [ ! -t 0 ]; then
        apply_pipeline_selection "lexicon,embedding,clustering,model1,model2,mosaic,regression"
        return
    fi

    while true; do
        echo ""
        echo "Which layers should the backend run with?"
        echo "  1) Full pipeline"
        echo "     lexicon, embedding, clustering, model1, model2, mosaic, regression"
        echo "  2) Core classifier pipeline"
        echo "     lexicon, embedding, clustering, model1, model2"
        echo "  3) Lexicon only"
        echo "     lexicon"
        echo "  4) Custom layer set"
        printf "Selection [1]: "
        read -r selection

        case "${selection:-1}" in
            1)
                apply_pipeline_selection "lexicon,embedding,clustering,model1,model2,mosaic,regression"
                break
                ;;
            2)
                apply_pipeline_selection "lexicon,embedding,clustering,model1,model2"
                break
                ;;
            3)
                apply_pipeline_selection "lexicon"
                break
                ;;
            4)
                echo "Available layers: ${CANONICAL_LAYERS[*]}"
                printf "Enter comma-separated layers: "
                read -r custom_layers
                if apply_pipeline_selection "${custom_layers}"; then
                    break
                fi
                echo "Please enter a valid comma-separated subset of the available layers."
                ;;
            *)
                echo "⚠️  Unrecognized selection. Please choose 1, 2, 3, or 4."
                ;;
        esac
    done
}

check_file() {
    if [ ! -f "$1" ]; then
        echo "⚠️  Missing: $1"
        MISSING=$((MISSING + 1))
    fi
}

check_dir_has_model() {
    local dir="$1"
    local name="$2"
    if [ ! -d "$dir" ]; then
        echo "⚠️  Missing checkpoint dir for ${name}: ${dir}"
        MISSING=$((MISSING + 1))
        return
    fi
    for ext in safetensors bin pt ckpt; do
        if ls "$dir"/*."$ext" 1>/dev/null 2>&1; then
            return 0
        fi
    done
    echo "⚠️  No model weights in ${dir} for ${name} (need .safetensors/.bin/.pt/.ckpt)"
    MISSING=$((MISSING + 1))
}

pipeline_has_layer() {
    local layer="$1"
    if [ -z "${PIPELINE_LAYERS_NORMALIZED}" ]; then
        return 0
    fi

    case ",${PIPELINE_LAYERS_NORMALIZED}," in
        *,"${layer}",*) return 0 ;;
        *) return 1 ;;
    esac
}

prompt_frontends "all"
prompt_pipeline_layers

echo ""
echo "Frontend selection: ${FRONTEND_SELECTION}"
echo "Pipeline selection: ${PIPELINE_LAYERS_NORMALIZED}"
print_pipeline_notes

activate_venv
WORKFLOW_ROOT="${ROOT}/backend/workflow"

echo "🧪 Running preflight checks..."
if [ "${KAYPOH_PREFLIGHT_STRICT:-1}" = "1" ]; then
    python3 "${ROOT}/scripts/preflight.py" --strict
else
    python3 "${ROOT}/scripts/preflight.py" || true
fi

MISSING=0

if pipeline_has_layer "clustering"; then
    check_file "${WORKFLOW_ROOT}/layer3-clustering/checkpoints/anomaly_detector.joblib"
fi

if pipeline_has_layer "model1"; then
    check_dir_has_model "${WORKFLOW_ROOT}/layer4-classification/model-1/checkpoints/best" "model1"
fi

if pipeline_has_layer "model2"; then
    check_dir_has_model "${WORKFLOW_ROOT}/layer4-classification/model-2/checkpoints/best" "model2"
fi

if pipeline_has_layer "regression"; then
    if [ ! -f "${WORKFLOW_ROOT}/layer6-regression/checkpoints/risk_regressor.json" ] || [ ! -f "${WORKFLOW_ROOT}/layer6-regression/checkpoints/metadata.json" ]; then
        echo "ℹ️  Optional regression checkpoint missing. Startup will continue without the regression layer."
    fi
fi

if [ "${MISSING}" -gt 0 ]; then
    echo ""
    echo "────────────────────────────────────────────────────"
    echo "  ${MISSING} checkpoint(s) missing."
    echo "  Train models first or download pre-trained weights."
    echo "  Startup is blocked to avoid degraded runtime."
    echo "────────────────────────────────────────────────────"
    echo ""
    if [ "${KAYPOH_ALLOW_PARTIAL_START:-0}" != "1" ]; then
        echo "Set KAYPOH_ALLOW_PARTIAL_START=1 only if you intentionally want degraded startup."
        exit 1
    fi
    export KAYPOH_FAIL_ON_LAYER_LOAD_ERROR="${KAYPOH_FAIL_ON_LAYER_LOAD_ERROR:-0}"
fi

echo "📦 Booting FastAPI backend on ${BACKEND_URL}..."
python3 -m uvicorn backend.main:app --host "${KAYPOH_HOST}" --port "${KAYPOH_PORT}" &
BACKEND_PID=$!

wait_for_backend_ready
emit_launch_telemetry_report "${FRONTEND_SELECTION}" || true

if selection_requires_demo_server; then
    start_demo_server
    open_selected_frontends
else
    echo "ℹ️  Backend is ready. No frontend opened."
fi

echo "✅ Services are running."
echo "   Backend: ${BACKEND_URL}"
print_selected_frontends
echo "Press Ctrl+C to stop everything."

wait "${BACKEND_PID}"
