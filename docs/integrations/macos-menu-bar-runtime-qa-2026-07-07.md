# macOS Menu-Bar Runtime QA Evidence

Date: 2026-07-07

Scope: local `JunasMenuBar.app` build/launch and sidecar process behavior for issue #94.

## Commands

```sh
./script/build_and_run.sh --verify
bash script/menu_bar_runtime_qa.sh
```

## Transcript

`./script/build_and_run.sh --verify` passed on macOS with exit code 0. Key output:

```text
Building for debugging...
Build complete!
```

`bash script/menu_bar_runtime_qa.sh` output:

```text
menu_bar_runtime_qa_start date=2026-07-07
menu_bar_runtime_qa_scenario=normal
sidecar_child_launch=pass
override_command=pass
normal_launch=pass
app_shutdown=pass
menu_bar_runtime_qa_scenario_result=pass
menu_bar_runtime_qa_scenario=unavailable
sidecar_unavailable=pass
override_unavailable_command=pass
menu_bar_runtime_qa_scenario_result=pass
menu_bar_runtime_qa_scenario=invalid_response
invalid_sidecar_response=pass
invalid_sidecar_error_class=NSError
menu_bar_runtime_qa_scenario_result=pass
menu_bar_runtime_qa_scenario=packaged_resource
packaged_resource_lookup=deferred
packaged_resource_deferred_reason=signed_dmg_task_bundles_sidecar
menu_bar_runtime_qa_scenario_result=pass
menu_bar_runtime_qa=pass
```

Packaged sidecar lookup uses `Contents/Resources/junas-sidecar/junas-sidecar`. The local `script/build_and_run.sh --bundle-only` path stages the SwiftPM app shell only, so bundling that executable is deferred to the signed DMG task.
