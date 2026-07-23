# 릴리스 절차 (수동)

1. `pyproject.toml` 버전 올리고 커밋 (`chore: v<ver>`)
2. `pip install -e .[release]` 후 `python scripts/build_release.py` → `dist/` 확인
3. 수동 스모크: `dist/horcrux.exe --help` → `dist/horcrux.exe init`으로 설정 생성 → `dist/horcrux.exe bot` 기동·로그인 확인
4. `git tag v<ver> && git push --tags`
5. GitHub Releases → 새 릴리스(태그 선택) → `dist/horcrux-<ver>-py3-none-any.whl` + `dist/horcrux.exe` 첨부 → 설명에 README 설치 섹션 링크
