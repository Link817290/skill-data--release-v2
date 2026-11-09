"""Reproduce the three pre-repair consumption failures from the issued project."""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile


def reproduce(project):
    logs = {}
    records = []
    with tempfile.TemporaryDirectory(prefix="cjson-oracle-before-") as temporary:
        root = Path(temporary)
        build = root / "build"
        original = root / "prefix-a"
        moved = root / "prefix-b"

        def run(label, argv, env=None, succeeds=True):
            result = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=120)
            output = result.stdout + result.stderr
            records.append({"label": label, "argv": argv, "exit_code": result.returncode,
                            "output_tail": output[-3000:]})
            if (result.returncode == 0) != succeeds:
                raise RuntimeError(f"unexpected pre-repair result for {label}: {output[-2000:]}")
            return output

        run("before_producer_configure", ["cmake", "-S", str(project), "-B", str(build),
            "-DBUILD_SHARED_AND_STATIC_LIBS=ON", "-DENABLE_CJSON_UTILS=ON",
            "-DENABLE_TARGET_EXPORT=ON", "-DENABLE_CJSON_TEST=OFF",
            f"-DCMAKE_INSTALL_PREFIX={original}"])
        run("before_producer_build", ["cmake", "--build", str(build), "-j2"])
        run("before_install", ["cmake", "--install", str(build)])
        consumer = root / "consumer"
        consumer.mkdir()
        (consumer / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.10)\nproject(before C)\n"
            "find_package(cJSON CONFIG REQUIRED)\nadd_executable(smoke main.c)\n"
            "target_link_libraries(smoke PRIVATE cjson_utils-static)\n", encoding="utf-8")
        (consumer / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        consumer_build = root / "consumer-build"
        run("before_static_consumer_configure", ["cmake", "-S", str(consumer), "-B",
            str(consumer_build), f"-DCMAKE_PREFIX_PATH={original}"])
        logs["build.log"] = run("before_static_consumer_link", ["cmake", "--build",
            str(consumer_build), "-j2"], succeeds=False)
        if "-lcjson_utils-static" not in logs["build.log"]:
            raise RuntimeError("static-consumer failure does not establish the missing imported target")

        shutil.copytree(original, moved)
        shutil.rmtree(original)
        logs["relocation.log"] = run("before_relocated_consumer_configure", ["cmake", "-S",
            str(consumer), "-B", str(root / "moved-consumer-build"),
            f"-DCMAKE_PREFIX_PATH={moved}"], succeeds=False)
        if "references the file" not in logs["relocation.log"] or str(original) not in logs["relocation.log"]:
            raise RuntimeError("relocation failure does not establish the removed-prefix import")

        environment = dict(os.environ, PKG_CONFIG_LIBDIR=str(moved / "lib/pkgconfig"))
        environment.pop("PKG_CONFIG_PATH", None)
        flags = run("before_pkg_config_query", ["pkg-config", "--cflags", "--libs", "libcjson_utils"],
                    env=environment)
        if str(original) not in flags:
            raise RuntimeError("original pkg-config metadata did not retain the old prefix")
        source = root / "pkg-consumer.c"
        source.write_text("#include <cjson/cJSON_Utils.h>\nint main(void) { return 0; }\n", encoding="utf-8")
        logs["pkg-config.log"] = flags + run("before_pkg_consumer_compile", ["cc", str(source),
            "-o", str(root / "pkg-consumer"), *shlex.split(flags)], succeeds=False)
        if "cJSON_Utils.h" not in logs["pkg-config.log"]:
            raise RuntimeError("pkg-config failure does not identify the unavailable public header")
    return logs, records
