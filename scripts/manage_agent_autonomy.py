#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path


def knowledge_block(finding: str) -> str:
    return f"""## Knowledge autonomy (addon)
- Respetá lecturas locales obligatorias. Si el contexto alcanza, no releas; si falta, consulta puntual directa con tools autorizadas, `knowledge-reader` para síntesis/corpus sólo si el rol permite delegar. Sin acceso, pedí contexto; sin bypass.
- Guardá sólo hallazgos confirmados y reutilizables ({finding}) al estabilizarse un hito, con `topic_key`; priorizá pedidos de recordar o restricciones críticas, según autoridad del rol.
- Summary sólo para continuidad nueva o si el contrato local lo exige expresamente; no reemplaza una memoria obligatoria. No duplicar lecturas/escrituras sin novedades ni guardar hipótesis/microiteraciones. No indexes corpus automáticamente."""


AGENT_RULES = {
    name: {"task_target": "knowledge-reader", "block": knowledge_block(finding)}
    for name, finding in {
        "plan": "decisiones o descartes",
        "build": "decisiones, bugfixes o aprendizajes",
        "planner": "decisiones o descartes",
        "master-dev": "decisiones, bugfixes o aprendizajes",
        "agent-design": "reglas de diseño del sistema",
    }.items()
}

MARKER_START = "<!-- KNOWLEDGE_AUTONOMY_START -->"
MARKER_END = "<!-- KNOWLEDGE_AUTONOMY_END -->"
TASK_COMMENT = "# knowledge-addon-autonomy"


def split_frontmatter(text: str) -> tuple[str, str, str]:
    if not text.startswith("---\n"):
        raise ValueError("Agent file without YAML frontmatter")
    second = text.find("\n---\n", 4)
    if second == -1:
        raise ValueError("Could not locate end of YAML frontmatter")
    frontmatter = text[4:second]
    body = text[second + 5 :]
    return "---\n", frontmatter, body


def patch_task(frontmatter: str, task_target: str) -> str:
    lines = frontmatter.splitlines()
    if any(TASK_COMMENT in line for line in lines):
        return frontmatter

    for index, line in enumerate(lines):
        if line.strip() == "task:":
            indent = line[: len(line) - len(line.lstrip())]
            insert_at = index + 1
            while insert_at < len(lines):
                candidate = lines[insert_at]
                if candidate.strip() and not candidate.startswith(indent + "  "):
                    break
                insert_at += 1
            lines.insert(insert_at, f"{indent}  {task_target}: allow  {TASK_COMMENT}")
            return "\n".join(lines)

    for index, line in enumerate(lines):
        if line.strip() != "permission:":
            continue
        indent = line[: len(line) - len(line.lstrip())]
        insert_at = index + 1
        while insert_at < len(lines):
            candidate = lines[insert_at]
            if candidate.strip() and not candidate.startswith(indent + "  "):
                break
            insert_at += 1
        lines[insert_at:insert_at] = [
            f"{indent}  task:  {TASK_COMMENT}",
            f'{indent}    "*": deny  {TASK_COMMENT}',
            f"{indent}    {task_target}: allow  {TASK_COMMENT}",
        ]
        return "\n".join(lines)

    return frontmatter


def unpatch_task(frontmatter: str) -> str:
    lines = [line for line in frontmatter.splitlines() if TASK_COMMENT not in line]
    return "\n".join(lines)


def patch_body(body: str, block: str) -> str:
    if MARKER_START in body:
        return body
    insertion = f"{MARKER_START}\n{block}\n{MARKER_END}\n\n"
    for anchor in ("Skills sugeridas:", "Skill sugerida:", "Entrega esperada:"):
        pos = body.find(anchor)
        if pos != -1:
            return body[:pos] + insertion + body[pos:]
    return body.rstrip() + "\n\n" + insertion


def unpatch_body(body: str) -> str:
    start = body.find(MARKER_START)
    if start == -1:
        return body
    end = body.find(MARKER_END, start)
    if end == -1:
        return body
    end += len(MARKER_END)
    while end < len(body) and body[end] in "\n\r":
        end += 1
    return body[:start] + body[end:]


def apply_to_agent(path: Path, rule: dict[str, str]) -> None:
    text = path.read_text()
    prefix, frontmatter, body = split_frontmatter(text)
    frontmatter = patch_task(frontmatter, rule["task_target"])
    body = patch_body(body, rule["block"])
    path.write_text(prefix + frontmatter + "\n---\n" + body)


def remove_from_agent(path: Path) -> None:
    text = path.read_text()
    prefix, frontmatter, body = split_frontmatter(text)
    frontmatter = unpatch_task(frontmatter)
    body = unpatch_body(body)
    path.write_text(prefix + frontmatter + "\n---\n" + body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply or remove knowledge autonomy on optional agents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_cmd = subparsers.add_parser("apply")
    apply_cmd.add_argument("--target-dir", required=True)

    remove_cmd = subparsers.add_parser("remove")
    remove_cmd.add_argument("--target-dir", required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    target_dir = Path(args.target_dir).expanduser()
    agents_dir = target_dir / "agents"

    for agent_name, rule in AGENT_RULES.items():
        path = agents_dir / f"{agent_name}.md"
        if not path.exists():
            continue
        if args.command == "apply":
            apply_to_agent(path, rule)
        else:
            remove_from_agent(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
