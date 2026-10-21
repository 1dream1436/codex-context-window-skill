"""Local Codex context settings. Python 3.11+, standard library only.

GPT/OpenAI local Work/Codex only. Global operations are transactional.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from contextlib import contextmanager
from pathlib import Path

VERSION = "0.4.0"
SCOPES = ("global-all", "global-model")
FIELDS = ("context_window", "max_context_window", "effective_context_window_percent", "auto_compact_token_limit")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def token_count(value):
    match = re.fullmatch(r"\s*([0-9]+)\s*(万|[kKmM])?\s*", str(value))
    if not match:
        raise ValueError("窗口请用正整数 token，或 60万、600k、1M。")
    factor = {None: 1, "万": 10000, "k": 1000, "m": 1000000}
    number = int(match[1]) * factor[match[2].lower() if match[2] else None]
    if number <= 0 or number > 2**63 - 1:
        raise ValueError("窗口必须是正的 64 位整数。")
    return number


def percentage(value):
    text = str(value).strip().removesuffix("%")
    if not text.isdigit() or not 1 <= int(text) <= 100:
        raise ValueError("有效比例必须是1到100之间的整数，可带%。")
    return int(text)


def bundled_catalog(codex=None):
    executable = str(codex) if codex else shutil.which("codex")
    if not executable:
        raise ValueError("找不到本机Codex；请用 --codex 指定已有的可执行文件，不自动安装。")
    try:
        # Even diagnostic startup may touch Codex state. Export bundled metadata
        # in a disposable home, never the user's live profile or cache.
        with tempfile.TemporaryDirectory(prefix="codex-bundled-") as isolated_home:
            environment = dict(os.environ, CODEX_HOME=isolated_home)
            result = subprocess.run([executable, "debug", "models", "--bundled"],
                                    capture_output=True, text=True, encoding="utf-8", timeout=30,
                                    env=environment,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise ValueError("本机Codex导出模型资料超过30秒，未写入配置。") from None
    if result.returncode:
        raise ValueError("本机Codex无法导出内置目录；请确认版本支持 debug models --bundled。")
    return json.loads(result.stdout), f"bundled:{executable}"


def root_key(text, key, value=None):
    """Edit one top-level TOML key, leaving sections and unrelated text intact."""
    lines = text.splitlines(keepends=True)
    boundary = next((i for i, line in enumerate(lines)
                     if re.match(r"\s*\[", line)), len(lines))
    pattern = re.compile(r"^\s*" + re.escape(key) + r"\s*=")
    top = [line for line in lines[:boundary] if not pattern.match(line)]
    if value is not None:
        if top and not top[-1].endswith(("\n", "\r")):
            top[-1] += "\n"
        top.append(f"{key} = {value}\n")
    result = "".join(top + lines[boundary:])
    tomllib.loads(result)
    return result


class ContextSettings:
    def __init__(self, home):
        self.home = Path(home).resolve()
        self.config_path = self.home / "config.toml"
        self.base = self.home / "context-window"
        self.catalog_path = self.base / "models.json"

    def config(self):
        text = self.config_path.read_text(encoding="utf-8-sig") if self.config_path.exists() else ""
        return text, tomllib.loads(text)

    def catalog_from(self, source):
        source = Path(source)
        data = read_json(source)
        return self.validate_catalog(data), str(source)

    @staticmethod
    def validate_catalog(data):
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            raise ValueError("模型资料需要包含 models 数组；请先用官方 debug models 刷新资料。")
        models = data["models"]
        if any(not isinstance(m, dict) for m in models):
            raise ValueError("模型资料的每个条目必须是对象。")
        slugs = [m.get("slug") for m in models]
        if not models or any(not isinstance(s, str) or not s for s in slugs) or len(set(slugs)) != len(slugs):
            raise ValueError("模型目录为空、slug 无效或重复。")
        return {"models": copy.deepcopy(models)}

    def resolve_source(self, source):
        source = Path(source).expanduser()
        return (source if source.is_absolute() else self.home / source).resolve()

    def catalog(self):
        _, config = self.config()
        source = config.get("model_catalog_json")
        if source:
            source = Path(source).expanduser()
            if not source.is_absolute():
                source = self.home / source
        else:
            source = self.home / "models_cache.json"
        return self.catalog_from(source)

    def recorded_overrides(self, catalog_bytes):
        state = self.recorded_parameters(catalog_bytes)
        if state is None:
            return None
        return {slug: values["context_window"] for slug, values in state["models"].items()
                if "context_window" in values}

    def recorded_parameters(self, catalog_bytes):
        """Read exact-hash records; migrate legacy window-only manifests without guessing."""
        backups = self.base / "backups"
        if not backups.exists():
            return None
        target_hash = digest(catalog_bytes)
        for path in sorted(backups.glob("*/manifest.json"), reverse=True):
            manifest = read_json(path)
            if not any(r["path"] == str(self.catalog_path) and
                       r["after_sha256"] == target_hash for r in manifest["files"]):
                continue
            operation = manifest.get("operation", {})
            if "desired_parameters" in operation:
                return copy.deepcopy(operation["desired_parameters"])
            if "desired_windows" in operation:
                return {"models": {slug: {"context_window": tokens}
                                   for slug, tokens in operation["desired_windows"].items()},
                        "all_models": {}}
        return None

    def current_parameters(self, source):
        if Path(source).resolve() != self.catalog_path.resolve():
            return {"models": {}, "all_models": {}}
        state = self.recorded_parameters(self.catalog_path.read_bytes())
        if state is None:
            raise ValueError("自定义目录缺少匹配的修改记录；停止，避免猜测应保留哪些参数。")
        return state

    @contextmanager
    def locked(self):
        self.base.mkdir(parents=True, exist_ok=True)
        lock = self.base / "mutation.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise ValueError("另一次上下文配置正在进行，请稍后重试。") from None
        try:
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            yield
        finally:
            lock.unlink(missing_ok=True)

    def transact(self, changes, metadata):
        # Windows wall-clock resolution can repeat even with time_ns().
        backup = self.base / "backups" / f"{time.time_ns()}-{time.monotonic_ns()}"
        backup.mkdir(parents=True)
        manifest = {"version": VERSION, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "operation": metadata, "files": []}
        for i, (path, after) in enumerate(changes):
            before = path.read_bytes() if path.exists() else None
            record = {"path": str(path), "existed": before is not None,
                      "before_sha256": digest(before), "after_sha256": digest(after),
                      "backup": f"{i}.bin" if before is not None else None}
            if before is not None:
                write_atomic(backup / record["backup"], before)
            manifest["files"].append(record)
        write_atomic(backup / "manifest.json", json_bytes(manifest))
        applied = []
        try:
            for (path, data), record in zip(changes, manifest["files"]):
                current = path.read_bytes() if path.exists() else None
                if digest(current) != record["before_sha256"]:
                    raise ValueError("配置同时被其他程序修改；未覆盖新内容。")
                write_atomic(path, data)
                applied.append(record)
        except Exception:
            for record in reversed(applied):
                path = Path(record["path"])
                if record["existed"]:
                    write_atomic(path, (backup / record["backup"]).read_bytes())
                else:
                    path.unlink(missing_ok=True)
            raise
        return str(backup / "manifest.json")

    def status(self):
        _, config = self.config()
        catalog, source = self.catalog()
        state = (self.recorded_parameters(self.catalog_path.read_bytes())
                 if Path(source).resolve() == self.catalog_path.resolve() else None)
        return {"status": "read_only", "catalog_source": source,
                "global_override": config.get("model_context_window"),
                "custom_model_windows": ({s: p["context_window"] for s, p in state["models"].items()
                                          if "context_window" in p} if state else {}),
                "custom_parameters": state,
                "explicit_compaction_limit": config.get("model_auto_compact_token_limit"),
                "compaction_counting_scope": config.get("model_auto_compact_token_limit_scope", "total"),
                "models": self.describe(catalog, config), "runtime_verified": False,
                "note": "预期值仅基于本机用户配置；进程、profile或受管策略覆盖需另查运行记录。"}

    @staticmethod
    def describe(catalog, config):
        models = []
        for m in catalog["models"]:
            base = m.get("context_window")
            if base is None:
                base = m.get("max_context_window")
            requested = config.get("model_context_window", base)
            cap = m.get("max_context_window")
            nominal = min(requested, cap) if requested is not None and cap is not None else requested
            pct = m.get("effective_context_window_percent", 95)
            usable = nominal * pct // 100 if nominal is not None else None
            compact = config.get("model_auto_compact_token_limit", m.get("auto_compact_token_limit"))
            compact_cap = nominal * 9 // 10 if nominal is not None else None
            expected = (compact_cap if compact is None else min(compact, compact_cap)) if compact_cap is not None else compact
            warnings = []
            if cap is not None and requested is not None and requested > cap:
                warnings.append("请求窗口超过目录max_context_window，预计被客户端限制。")
            if compact is not None and expected != compact:
                warnings.append("压缩设置超过窗口90%，预计被客户端限制。")
            if usable is not None and expected is not None and expected > usable:
                warnings.append("预计压缩阈值高于可用窗口；请核对运行行为。")
            models.append({"model": m["slug"], "catalog_window": base,
                           "configured_window": requested, "max_context_window": cap,
                           "expected_raw_window": nominal, "effective_context_window_percent": pct,
                           "expected_effective_window": usable,
                           "configured_compaction_limit": compact,
                           "expected_compaction_limit": expected, "warnings": warnings})
        return models

    def set_global(self, scope, tokens=None, model=None, effective_percent=None,
                   auto_compact_limit="keep", preview=False):
        if scope not in SCOPES:
            raise ValueError("set_global 仅接受 global-all 或 global-model。")
        if scope == "global-model" and not model:
            raise ValueError("单模型范围需要 model。")
        if scope == "global-all" and model:
            raise ValueError("全部模型范围不能同时指定model。")
        tokens = None if tokens in (None, "keep") else token_count(tokens)
        pct = None if effective_percent in (None, "keep") else percentage(effective_percent)
        compact = auto_compact_limit
        if compact not in ("keep", "default"):
            compact = token_count(compact)
        if tokens is None and pct is None and compact == "keep":
            raise ValueError("至少指定一项要修改的参数。")
        with self.locked():
            text, config = self.config()
            catalog, source = self.catalog()
            state = self.current_parameters(source)
            entries = {m["slug"]: m for m in catalog["models"]}
            if scope == "global-model" and model not in entries:
                raise ValueError(f"当前模型目录没有 {model}；不创建猜测的模型条目。")
            targets = list(entries) if scope == "global-all" else [model]
            changes = []
            materialized = False
            compact_materialized = False
            catalog_needed = scope == "global-model" or pct is not None
            using_managed = Path(source).resolve() == self.catalog_path.resolve()
            # A scalar override masks the corresponding per-model value. Only
            # materialize axes explicitly changed, retaining other model choices.
            if scope == "global-model":
                old_override = config.get("model_context_window")
                if tokens is not None and old_override is not None:
                    for m in catalog["models"]:
                        cap = m.get("max_context_window")
                        m["context_window"] = min(old_override, cap) if cap is not None else old_override
                        state["models"].setdefault(m["slug"], {})["context_window"] = m["context_window"]
                    text = root_key(text, "model_context_window")
                    materialized = True
                old_compact = config.get("model_auto_compact_token_limit")
                if compact != "keep" and old_compact is not None:
                    if config.get("model_auto_compact_token_limit_scope", "total") != "total":
                        raise ValueError("当前全局压缩按body_after_prefix计数，无法无损转换为单模型设置；未修改配置。")
                    for m in catalog["models"]:
                        m["auto_compact_token_limit"] = old_compact
                        state["models"].setdefault(m["slug"], {})["auto_compact_token_limit"] = old_compact
                    text = root_key(text, "model_auto_compact_token_limit")
                    compact_materialized = True
            elif tokens is not None:
                text = root_key(text, "model_context_window", str(tokens))

            if compact == "default":
                # Obtain actual current model defaults; do not infer them from a
                # pinned custom catalog or replace them with a fixed percentage.
                defaults, _ = self.catalog_from(self.home / "models_cache.json")
                default_entries = {m["slug"]: m for m in defaults["models"]}
                for slug in targets:
                    if slug not in default_entries:
                        raise ValueError(f"本机新资料缺少 {slug}，无法确认默认压缩设置。")
                    value = default_entries[slug].get("auto_compact_token_limit")
                    if value is None:
                        entries[slug].pop("auto_compact_token_limit", None)
                    else:
                        entries[slug]["auto_compact_token_limit"] = value
                    state["models"].setdefault(slug, {}).pop("auto_compact_token_limit", None)
                if scope == "global-all":
                    text = root_key(text, "model_auto_compact_token_limit")
                    text = root_key(text, "model_auto_compact_token_limit_scope")
                    catalog_needed = catalog_needed or using_managed or any(
                        m.get("auto_compact_token_limit") != default_entries[m["slug"]].get("auto_compact_token_limit")
                        for m in self.catalog()[0]["models"])
            elif compact != "keep" and scope == "global-all":
                text = root_key(text, "model_auto_compact_token_limit", str(compact))

            if pct is not None and scope == "global-all":
                state["all_models"]["effective_context_window_percent"] = pct
            for slug in targets:
                chosen = state["models"].setdefault(slug, {})
                if tokens is not None and scope == "global-model":
                    entries[slug]["context_window"] = tokens
                    chosen["context_window"] = tokens
                if pct is not None:
                    entries[slug]["effective_context_window_percent"] = pct
                    if scope == "global-model":
                        chosen["effective_context_window_percent"] = pct
                    else:
                        chosen.pop("effective_context_window_percent", None)
                if compact not in ("keep", "default") and scope == "global-model":
                    entries[slug]["auto_compact_token_limit"] = compact
                    chosen["auto_compact_token_limit"] = compact
            state["models"] = {s: p for s, p in state["models"].items() if p}
            next_config = tomllib.loads(text)
            planned_models = self.describe(catalog, next_config)
            if compact not in ("keep", "default"):
                for m in planned_models:
                    if m["model"] not in targets:
                        continue
                    raw = m["expected_raw_window"]
                    usable = m["expected_effective_window"]
                    if raw is None or usable is None:
                        raise ValueError(f"{m['model']}缺少窗口资料，无法校验压缩阈值。")
                    limit = min(raw * 9 // 10, usable)
                    if compact > limit:
                        raise ValueError(f"{m['model']}压缩阈值{compact}超过预计允许值{limit}；未写入，请调整参数。")
            if catalog_needed:
                text = root_key(text, "model_catalog_json", json.dumps(self.catalog_path.as_posix()))
                changes.append((self.catalog_path, json_bytes(catalog)))
            changes.append((self.config_path, text.encode("utf-8")))
            changes = [(p, b) for p, b in changes
                       if p == self.catalog_path or not p.exists() or p.read_bytes() != b]
            metadata = {"scope": scope, "model": model, "tokens": tokens,
                        "effective_percent": pct, "auto_compact_limit": compact,
                        "desired_parameters": state}
            result = {"status": "preview" if preview else "unchanged", "scope": scope, "model": model,
                "requested_tokens": tokens,
                "catalog_source": source, "existing_global_override_materialized": materialized,
                "existing_global_compaction_materialized": compact_materialized,
                "parameters": metadata, "models": planned_models,
                "runtime_verified": False,
                "next_action": "重新加载本地桌面应用后，以 token_count 的 model_context_window 核对。"}
            result["backup_manifest"] = None
            if changes and not preview:
                result["backup_manifest"] = self.transact(changes, metadata)
                result["status"] = "saved_requires_reload"
            return result

    def refresh_catalog(self, source=None, apply=False, refresh_from_bundled=False, codex=None):
        """Refresh metadata from local cache, explicit file or installed Codex."""
        if source and refresh_from_bundled:
            raise ValueError("--source和--refresh-from-bundled不能同时使用。")
        if codex and not refresh_from_bundled:
            raise ValueError("--codex仅与--refresh-from-bundled配合使用。")
        with self.locked():
            _, config = self.config()
            configured = config.get("model_catalog_json")
            if not configured or self.resolve_source(configured) != self.catalog_path.resolve():
                raise ValueError("当前未使用本技能的模型目录；无需刷新。")
            if not self.catalog_path.exists():
                raise ValueError("本技能的模型目录不存在。")
            if refresh_from_bundled:
                data, source_name = bundled_catalog(codex)
                incoming = self.validate_catalog(data)
            else:
                source = Path(source).expanduser().resolve() if source else self.home / "models_cache.json"
                if source.resolve() == self.catalog_path.resolve():
                    raise ValueError("刷新来源不能是当前自定义目录。")
                incoming, source_name = self.catalog_from(source)
            current, _ = self.catalog_from(self.catalog_path)
            state = self.current_parameters(self.catalog_path)
            incoming_by_slug = {m["slug"]: m for m in incoming["models"]}
            missing = sorted(set(state["models"]) - set(incoming_by_slug))
            if missing:
                raise ValueError("新目录缺少已自定义的模型：" + ", ".join(missing))
            old_by_slug = {m["slug"]: m for m in current["models"]}
            new_models = sorted(set(incoming_by_slug) - set(old_by_slug))
            removed_models = sorted(set(old_by_slug) - set(incoming_by_slug))
            default_changes = {}
            for slug, model in incoming_by_slug.items():
                if slug in old_by_slug:
                    differences = {f: {"old": old_by_slug[slug].get(f), "new": model.get(f)}
                                   for f in FIELDS if old_by_slug[slug].get(f) != model.get(f)
                                   and f not in state["models"].get(slug, {})
                                   and f not in state["all_models"]}
                    if differences:
                        default_changes[slug] = differences
                model.update(state["all_models"])
                model.update(state["models"].get(slug, {}))
            described = self.describe(incoming, config)
            for m in described:
                chosen = state["models"].get(m["model"], {})
                compact = chosen.get("auto_compact_token_limit")
                if compact is not None and (compact > m["expected_compaction_limit"] or
                                           (m["expected_effective_window"] is not None and
                                            compact > m["expected_effective_window"])):
                    raise ValueError(f"新版资料使{m['model']}的自定义压缩阈值不再适用；未写入，请先调整。")
            after = json_bytes(incoming)
            changed = after != self.catalog_path.read_bytes()
            result = {"status": "preview" if not apply else "unchanged",
                      "source": source_name, "new_models": new_models,
                      "removed_models": removed_models, "default_parameter_changes": default_changes,
                      "preserved_custom_windows": {s: p["context_window"] for s, p in state["models"].items()
                                                   if "context_window" in p},
                      "preserved_parameters": state, "models": described, "catalog_changed": changed,
                      "runtime_verified": False}
            if apply and changed:
                result["backup_manifest"] = self.transact(
                    [(self.catalog_path, after)],
                    {"scope": "refresh", "source": source_name, "desired_parameters": state})
                result["status"] = "saved_requires_reload"
            return result

    def restore(self, manifest_path):
        with self.locked():
            manifest_path = Path(manifest_path).resolve()
            if not manifest_path.is_relative_to((self.base / "backups").resolve()):
                raise ValueError("只接受本技能 backups 目录中的清单。")
            manifest = read_json(manifest_path)
            allowed = {str(self.config_path), str(self.catalog_path)}
            for record in manifest["files"]:
                if record["path"] not in allowed:
                    raise ValueError("备份清单包含非本技能管理的路径。")
                path = Path(record["path"])
                current = path.read_bytes() if path.exists() else None
                if digest(current) != record["after_sha256"]:
                    raise ValueError("修改后配置又有变化；停止自动回滚，避免覆盖其他修改。")
                if record["existed"]:
                    saved = manifest_path.parent / record["backup"]
                    if saved.parent != manifest_path.parent or digest(saved.read_bytes()) != record["before_sha256"]:
                        raise ValueError("备份内容校验失败。")
            for record in reversed(manifest["files"]):
                path = Path(record["path"])
                if record["existed"]:
                    write_atomic(path, (manifest_path.parent / record["backup"]).read_bytes())
                else:
                    path.unlink(missing_ok=True)
        return {"status": "restored_requires_reload", "runtime_verified": False}

def main():
    # Windows pipes otherwise inherit a legacy locale encoding for Chinese JSON.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default=os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    setter = commands.add_parser("set")
    setter.add_argument("--scope", choices=SCOPES, required=True)
    setter.add_argument("--tokens", help="窗口token数；省略或keep则保持")
    setter.add_argument("--model")
    setter.add_argument("--effective-percent", help="有效比例1-100；省略或keep则保持")
    setter.add_argument("--auto-compact-limit", default="keep", help="keep、default或token数")
    setter.add_argument("--preview", action="store_true", help="仅预览，不修改配置和模型目录")
    restore = commands.add_parser("restore")
    restore.add_argument("manifest")
    refresh = commands.add_parser("refresh")
    refresh.add_argument("--source", help="新模型目录 JSON；默认使用本机 models_cache.json")
    refresh.add_argument("--apply", action="store_true", help="确认预览后写入")
    refresh.add_argument("--refresh-from-bundled", action="store_true", help="从本机Codex导出内置目录")
    refresh.add_argument("--codex", help="已有Codex可执行文件路径；只用于内置目录来源")
    args = parser.parse_args()
    try:
        settings = ContextSettings(args.home)
        if args.command == "status":
            result = settings.status()
        elif args.command == "restore":
            result = settings.restore(args.manifest)
        elif args.command == "refresh":
            result = settings.refresh_catalog(args.source, args.apply, args.refresh_from_bundled, args.codex)
        else:
            result = settings.set_global(args.scope, args.tokens, args.model,
                                         args.effective_percent, args.auto_compact_limit, args.preview)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc), "runtime_verified": False}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
