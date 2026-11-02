# core/skills.py —— Skill 发现与动态加载
# 初始化时扫描 .agents/skills/ 子目录，只提取 SKILL.md 的 name / description
# 正文与附件内容由 loadSkill 工具按需读取，不常驻内存
import os
from pathlib import Path

# Skill 根目录候选列表：优先扫描老师指定的 Office 目录，
# 再扫描项目自带的 .agents/skills，两者有 Skill 都会被发现
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_ROOT_CANDIDATES = [
    Path("E:/Office/.agents/skills"),          # 老师的作业运行目录（优先）
    _PROJECT_ROOT / ".agents" / "skills",       # 项目自带 Skill
]
AGENTS_ROOT = AGENTS_ROOT_CANDIDATES[0]        # 默认取第一个


# ========== Frontmatter 解析（支持单行 + YAML 多行 description） ==========
import re

# 单行 name 匹配
_NAME_PATTERNS = [
    re.compile(r"^name\s*:\s*(?P<v>.+?)\s*$", re.IGNORECASE),
    re.compile(r"^name\s*=\s*(?P<v>.+?)\s*$", re.IGNORECASE),
]

# 单行 description 匹配
_DESC_LINE_PATTERNS = [
    re.compile(r'^description\s*:\s*["\']?(?P<v>.+?)["\']?\s*$', re.IGNORECASE),
    re.compile(r'^description\s*=\s*["\']?(?P<v>.+?)["\']?\s*$', re.IGNORECASE),
]

# description: | 或 description: > —— 多行折叠标记
_DESC_BLOCK_PATTERN = re.compile(r"^description\s*:\s*[|>]\s*$", re.IGNORECASE)


def _parse_frontmatter(text: str) -> dict:
    """从 SKILL.md 头部 YAML Frontmatter 解析 name / description
    兼容格式：
      name: python-helper          # 单行
      description: "xxx"           # 单行引号
      description: |               # YAML 多行文本块
        第一行
        第二行
    """
    info = {}
    lines = text.split("\n", 50)
    if not lines or lines[0].strip() != "---":
        return info

    in_desc_block = False
    desc_lines = []

    for i, line in enumerate(lines[1:], start=1):
        stripped = line.strip()
        if stripped == "---":
            # Frontmatter 结束
            break

        if in_desc_block:
            # 多行 description：收集缩进行
            if line.startswith((" ", "\t")):
                desc_lines.append(stripped)
            else:
                # 遇到非缩进行，说明多行块结束了
                in_desc_block = False
                if desc_lines and "description" not in info:
                    info["description"] = " ".join(desc_lines)
                # 回退处理这一行（可能是另一个字段）
                # 不用 continue，让后面的逻辑处理

        if in_desc_block:
            continue   # 还在多行块里，跳过正常字段匹配

        # —— 尝试多行 description 起始 ——
        if _DESC_BLOCK_PATTERN.match(stripped):
            in_desc_block = True
            desc_lines = []
            continue

        # —— 尝试单行 name ——
        matched = False
        for pat in _NAME_PATTERNS:
            m = pat.match(stripped)
            if m:
                raw = m.group("v").strip().strip('"').strip("'")
                if raw:
                    info["name"] = raw
                matched = True
                break
        if matched:
            continue

        # —— 尝试单行 description ——
        for pat in _DESC_LINE_PATTERNS:
            m = pat.match(stripped)
            if m:
                raw = m.group("v").strip().strip('"').strip("'")
                if raw:
                    info["description"] = raw
                break

    # 如果循环结束还在多行块里
    if in_desc_block and desc_lines and "description" not in info:
        info["description"] = " ".join(desc_lines)

    return info


def discover_skills(root: Path | None = None) -> list:
    """扫描一个或多个 .agents/skills 目录，返回 [{name, description, path}]
    - root=None 时，依次扫描 AGENTS_ROOT_CANDIDATES 所有存在的目录
    - root 传 Path 时，只扫描那一个（兼容单目录调用）
    重名 Skill 先扫描到的优先（Office 目录优先）
    """
    skills = []
    seen_names = set()

    roots = [root] if root else AGENTS_ROOT_CANDIDATES

    for scan_root in roots:
        if not scan_root.is_dir():
            continue
        for child in sorted(scan_root.iterdir()):
            if not child.is_dir():
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.is_file():
                continue
            try:
                with open(skill_md, "r", encoding="utf-8") as f:
                    head = f.read(4096)
            except Exception:
                continue
            fm = _parse_frontmatter(head)
            name = fm.get("name") or child.name
            desc = fm.get("description", "无描述")
            # Office 目录优先，同名 Skill 项目自带的跳过
            if name in seen_names:
                continue
            seen_names.add(name)
            skills.append({
                "name": name,
                "description": desc,
                "path": str(child),
            })
    return skills


def _resolve_file(skill_path: Path, filename: str) -> Path | None:
    """在指定 Skill 目录内查找 filename：
    - 若 filename 直接存在于 skill_path 下，返回
    - 否则递归 skill_path，匹配唯一同名文件返回；多个候选则返回 None（交给 LLM 决定）
    """
    direct = skill_path / filename
    if direct.is_file():
        return direct
    # 递归搜索
    candidates = list(skill_path.rglob(filename))
    if len(candidates) == 1:
        return candidates[0]
    return None


def load_skill(skills: list, name: str, filename: str | None = None) -> str:
    """loadSkill 工具实现：
    - name 必须匹配 discover_skills 中某个 skill 的 name 或目录名
    - 未传 filename：返回 SKILL.md 全文
    - 传了 filename：返回该附件内容（不再重复加载 SKILL.md）
    - 文件路径限制在 skill 目录内，避免越权读取
    """
    if not name:
        return "错误：name 参数不能为空"

    # 匹配 Skill：先精确匹配 name，再匹配目录名
    matched = None
    for s in skills:
        if s["name"] == name or Path(s["path"]).name == name:
            matched = s
            break
    if matched is None:
        available = [s["name"] for s in skills] or "（未发现任何 Skill）"
        return f"错误：未找到名为「{name}」的 Skill。可用 Skill：{available}"

    skill_path = Path(matched["path"])

    if not filename:
        # 只加载 SKILL.md 正文
        target = skill_path / "SKILL.md"
        if not target.is_file():
            return f"错误：{skill_path} 下未找到 SKILL.md"
        try:
            text = target.read_text(encoding="utf-8")
        except Exception as e:
            return f"错误：读取 SKILL.md 失败 -> {e}"
        return (f"【Skill：{matched['name']}】\n"
                f"描述：{matched['description']}\n"
                f"路径：{skill_path}\n\n"
                f"{text}")

    # 加载附件文件
    filename = filename.strip()
    target = _resolve_file(skill_path, filename)
    if target is None:
        # 找不到或多匹配
        candidates = list(skill_path.rglob(filename))
        if not candidates:
            return f"错误：在 Skill 目录 {skill_path} 下未找到文件 {filename}"
        # 多个候选，列出路径由 LLM 决定
        lines = [f"在 Skill {matched['name']} 下找到多个同名文件 {filename}，请指定其中一个："]
        for c in candidates:
            lines.append(f"  - {c.relative_to(skill_path)}")
        lines.append("（建议传入完整相对路径，例如 docs/reference.md）")
        return "\n".join(lines)

    # 安全校验：target 必须在 skill_path 内（防路径穿越）
    try:
        target.resolve().relative_to(skill_path.resolve())
    except ValueError:
        return f"错误：目标文件不在 Skill 目录内，已拒绝 -> {target}"

    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return (f"错误：{target} 不是纯文本文件，无法按 UTF-8 读取。"
                f"Skill 仅支持 .md/.txt/.py/.json 等文本附件")
    except Exception as e:
        return f"错误：读取附件失败 -> {e}"

    rel = target.relative_to(skill_path)
    return (f"【Skill {matched['name']} 附件】{rel}\n\n{text}")
