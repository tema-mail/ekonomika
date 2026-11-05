#!/bin/zsh
# Пересобирает дашборд из свежих данных и выкладывает закрытую страницу: ~/Sites/ekonomika/obnovit.sh
# Аргумент --lokalno: только собрать, без git push.
set -e
cd "$HOME/Sites/ekonomika"
export PATH="$HOME/.local/node/bin:$PATH"
mkdir -p dannye/vps
(cd dannye/vps && ssh -o ConnectTimeout=10 -o BatchMode=yes claude-vps "cd ~/.claude/projects && find . -maxdepth 2 -name '*.jsonl' -print0 | xargs -0 -r tar cz" | tar xz) || echo "VPS недоступен: беру прошлую копию"
python3 scripts/chaty.py "$HOME/.claude/projects" "$PWD/dannye/vps" > dannye/chaty.json
ID=$(python3 -I -c "import json,os;print(json.load(open(os.path.expanduser('~/.config/finansy/sheets.json')))['dds'])")
curl -sL --max-time 60 -o dannye/dds.new "https://docs.google.com/spreadsheets/d/$ID/export?format=csv&gid=1603447614" && [ -s dannye/dds.new ] && mv dannye/dds.new dannye/dds.csv || echo "ДДС не скачался: беру прошлую копию"
python3 scripts/sobrat.py dannye/chaty.json dannye/dds.csv
[ -d node_modules ] || npm i --silent
rm -rf dist; npx astro build >/dev/null
node scripts/zamok.mjs
rm -rf site; cp -R dist site
[ "$1" = "--lokalno" ] && exit 0
git add site && git commit -qm "Данные дашборда: обновление $(date +%d.%m.%Y)" && git push -q || echo "Нечего выкладывать"
echo "Готово: https://tema-mail.github.io/ekonomika/"
