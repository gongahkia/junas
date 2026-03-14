package com.gongahkia.kilter_together_mobile

import android.os.StatFs
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.android.FlutterActivity
import io.flutter.plugin.common.MethodChannel
import java.io.File

class MainActivity : FlutterActivity() {
    private val storageChannelName = "kilter_together/catalog_storage"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            storageChannelName,
        ).setMethodCallHandler { call, result ->
            val path = call.argument<String>("path")
            if (path.isNullOrBlank()) {
                result.error("invalid_args", "Path is required.", null)
                return@setMethodCallHandler
            }

            when (call.method) {
                "availableBytes" -> {
                    try {
                        val target = File(path)
                        val existingPath = if (target.exists()) target.absolutePath else target.parentFile?.absolutePath
                        if (existingPath.isNullOrBlank()) {
                            result.error("space_check_failed", "Unable to inspect available device storage.", null)
                            return@setMethodCallHandler
                        }
                        val statFs = StatFs(existingPath)
                        result.success(statFs.availableBytes)
                    } catch (error: Exception) {
                        result.error(
                            "space_check_failed",
                            "Unable to inspect available device storage.",
                            error.localizedMessage,
                        )
                    }
                }

                "excludeFromBackup" -> result.success(null)
                else -> result.notImplemented()
            }
        }
    }
}
