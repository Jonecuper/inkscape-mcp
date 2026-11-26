---
name: inkscape-mcp
description: Установка, подключение и работа с Inkscape MCP-сервером (sandraschi/inkscape-mcp) — создание и правка векторной графики, экспорт PNG/PDF, слои, анимации, LPE. Используй когда пользователь просит настроить Inkscape MCP, перенести его на другой компьютер, или сделать векторную графику через эти MCP-инструменты.
---

# Inkscape MCP — установка и работа

Навык для сервера https://github.com/sandraschi/inkscape-mcp (v3.4.5, проверено 2026-11).
Состояние текущей машины можно проверить по разделу «Статус» ниже — если сервер уже
подключён, сразу к «Как рисовать», ничего не переустанавливать.

## Статус (как проверить)

```bash
claude mcp list   # строка "inkscape: ... - ✔ Connected"
```

Инструменты `mcp__inkscape__*` видны только в сессиях, запущенных ПОСЛЕ
`claude mcp add` — в текущей их может не быть; в этом случае тестируй напрямую
через FastMCP-клиент (рецепт ниже) и предупреди пользователя про перезапуск.

## Установка с нуля (Windows 10/11)

Нужны: Inkscape 1.2+ (проверить `inkscape --version`), `uv`, `git`. bun/Python-venv/веб-зависимости досставляет сам `start.bat`.

Выполни скрипт из этого навыка (он делает check → install → mcp add идемпотентно):

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<папка навыка>/scripts/setup.ps1" -TargetDir "C:/dev/tools/inkscape-mcp"
```

ВАЖНО при правке setup.ps1: файл обязан остаться UTF-8 **с BOM** — Windows PowerShell 5.1
иначе ломает кириллицу в парсер (редакторы/Write обычно пишут без BOM; чинить так:
`[IO.File]::WriteAllText($p,[IO.File]::ReadAllText($p,[Text.UTF8Encoding]::new($false)),[Text.UTF8Encoding]::new($true))`).
Нюанс новой машины: winget ставит bun в `%USERPROFILE%\.bun\bin`, PATH подхватится только
после переулога — если `-Check` пишет `bun: install`, а `start.bat -Yes -NoStart` уже
отработал OK, это не ошибка, просто проверка не видит bun в текущем PATH.

Или вручную по шагам (их документация docs/AI_SETUP.md):

1. `git clone --depth 1 https://github.com/sandraschi/inkscape-mcp.git C:/dev/tools/inkscape-mcp`
2. Проверка (ничего не ставит): `cmd //c "C:/dev/tools/inkscape-mcp/start.bat -Check -Json"`
   — парси `verdict`: READY → продолжать; BLOCKED → остановиться и показать `detail`+`fix`.
3. Установка (~2–4 мин, не прерывать): `cmd //c "C:/dev/tools/inkscape-mcp/start.bat -Yes -NoStart"` → финал `Install OK.`
4. Подключение: `claude mcp add inkscape --scope user -- uv --directory "C:/dev/tools/inkscape-mcp" run inkscape-mcp --mode stdio`
5. Опциональный дашборд: `start.bat -Yes -Detach -NoBrowser`; health: `http://127.0.0.1:11028/api/health`, UI: `http://127.0.0.1:11029`; стоп: `stop.bat`.

### Подводные камни

- Из MSYS/Git-Bash пути `C:\...` для cmd разворачиваются сломанно (бэклэши съедаются:
  `"C:devtools..."`). Всегда прямые слеши: `cmd //c "C:/dev/tools/inkscape-mcp/start.bat ..."`
  — .bat сам делает `cd /d "%~dp0"`, рабочий каталог не важен.
- Первый `uv sync` долгий; таймаут ставь ≥ 600 с, не убивай молчащий процесс.
- Не редактируй исходники репозитория для «починки» — это их обещание из AI_SETUP; починки — поверх (см. «Пустышки»).
- **Лаг записи PNG**: экспорт inkscape (CLI и серверный export_preview) физически пишет файл с
  задержкой в несколько секунд — сразу после «success» файл может ещё НЕ существовать.
  Читать превью надо с `sleep 3`+повтором, иначе берёшь stale-файл и делаешь ложные выводы
  (на этом были спотыкания: «одинаковые профили», «NOT found», «сервер не перезаписывает»).
- **Новые шрифты Windows**: instancer из VF сохраняет устаревшие name ID1/16 — чинить name-таблицу
  (обе платформы, ID1/2/16/17). Per-user установка (HKCU+кэш) может не подхватываться без переулога;
  AddFontResourceEx(fl=0) грузит на сессию, но файл после этого залочен — для обновлений брать
  новое имя файла. Самый надёжный путь для точной работы — читать контуры глифов напрямую из TTF
  fontTools'ом (SVGPathPen+TransformPen, y-флип scale(s,-s)), без участия системы шрифтов.

## Инструменты (19) и что из них честно

Инструменты-«портманто» (группы операций): `inkscape_file`, `inkscape_vector`, `inkscape_render`,
`inkscape_layers`, `inkscape_animation`, `inkscape_analysis`, `inkscape_validation`,
`inkscape_system`, `inkscape_fleet`, `inkscape_fab_art`, `inkscape_sim_art`,
`generate_heraldry`, `generate_svg`, `llm_ops`, `list_local_models`, `inkscape_shutdown`,
`agentic_inkscape_workflow`, `intelligent_vector_processing`, `conversational_inkscape_assistant`.

Проверено энд-ту-энд (2026-11-26):

- ✅ `inkscape_vector create_object` — создаёт фигуру, НО каждый вызов ПЕРЕЗАПИСЫВАЕТ
  документ (нельзя «налепить» несколько фигур подряд; для композиций — `construct_svg`
  с готовым body-XML или правка SVG напрямую как текста).
- ✅ `inkscape_render export_preview` — PNG для vision-цикла; работает с dpi (помнить про лаг записи!).
- ✅ `inkscape_vector text_to_path` (проверено 2026-11-26) — реально конвертирует <text> в контуры.
- ✅ `inkscape_file convert|info|validate` — настоящий `inkscape --actions` (SVG→PDF/PNG/EPS/DXF).
- ✅ `generate_heraldry operation=trumponia` — полноценная векторная композиция с градиентами.
- ❌ `trace_image` — ЛЖЁТ: возвращает success:true, не создавая файл (дёргает
  несуществующее действие `selection-trace`). Для растер→вектор используй standalone
  `potrace`/`vtracer` или ручную подгонку геометрии с численным поиском по маске.
- ❌ `generate_barcode_qr` — рисует текст моноширинным шрифтом вместо матрицы QR.
  Для реальных QR — `pip install qrcode` + экспорт PNG, или SVG-матрицу собрать руками.
- ❌ `path_simplify`/`scour_svg` (2026-11-26) — «success», но файл после них КРУПНЕЕ
  оригинала (пере-сериализация без упрощения). Минимизацию SVG делать своими ногами:
  bake transform→DP по якорям→пересборка кривых Catmull-Rom с хвостами ≤1/3 отрезка
  (иначе шипы на углах); скрипт-эталон: scripts/smoothmin.py (в этой папке навыка).
  Бонус: тот же приём лечит «лесенки» пиксель-трейса при зуме (staircase от ~1px-сегментов
  vtracer) — чередить якоря и перестраивать сглаженные кривые, а не просто удалять точки.

## Recipe: пиксель-перфект текст из растра (vtracer, обошёл фейковый trace_image)

Проверено 2026-11-26, IoU к оригиналу 0.995:
1. Сегментировать маску цвета на connected components (BFS), по глифу.
2. Кэш глифа → PIL: маска 1×, bicubic ×3, GaussianBlur 1.2, порог >118, INVERT (vtracer binary: чёрный=объект; инвертированный даёт «рамка+дырка», фильтровать субпуть, охватывающий всё изображение).
3. vtracer.convert_image_to_svg_py(colormode="binary", hierarchical="sequence", mode="spline", filter_speckle=4) — запускать через `uv run --no-project --with vtracer`.
4. Маппинг НЕ через PAD-арифметику: парсить d (M/C якоря, игнорить контрольные точки C), сдвиг translate = целевой bbox − min(якорей). Контрольные точки сплайнов вылезают за глиф — по ним ориентироваться нельзя.
5. Финальный калибровочный сдвиг группы ~+0.5 канвас-ед. (AA-пороги трейса vs маски).
6. Проверять IoU рендер vs оригинал (тот же экспорт через сервер), а не «на глаз».

## Растер → ЧИСТЫЙ вектор: проверенная иерархия (итог проекта 2026-11-26)

Главный вывод: полностью автоматической «чистой» векторизации (мало примитивов, прямые
— прямые, дуги — дуги) НЕ существует: трейсеры верны пиксельной границе, а она = AA-лесенка.
Поэтому методы выстроены от чистого к «плотному, но точному»:

0. **Официальный SVG бренда** — сначала искать, не рисовать.
0.5. **РУЧНАЯ доводка трейса в Inkscape — лучший известный результат (проверено 2026-11-26)**:
   взять полный пиксель-трейс (этот же мастер даёт 1419 узлов), выделить ОДИН объект,
   Path > Simplify (Ctrl+_), затем Node tool удалять лишние узлы — оставшиеся перераспределяются
   плавно; Inkscape сам восстанавливает истинные дуги (команды A) на скруглениях. Результат
   пользователя: 386 узлов (−73%), IoU неотличим от мастера, зум 8× чистый, ~1.5 ч на весь логотип.
   Это и есть недостающее звено: автоматика (пп.1-3) доводит до 90%, последние 10% качества
   дешевле руками, чем алгоритмами.
1. **ТИПОГРАФИКА — через шрифт, не через трейс** (самый чистый результат, см. пайплайн ниже).
2. **Самописные надписи/логотипы без шрифта**: пиксель-трейс + геометрическая подгонка
   (`scripts/fitgeom3.py`: medsmooth якорей → КОНКУРЕНЦИЯ покрытий прямая/дуга → snap к
   0/90/45 → проекция стыков). Важно: НЕ прореживать DP-узлами (они режут дуги на фасетки) —
   классифицировать жадным ростом региона. Результат: L/A/C ~18 примитивов/букву, лесенок нет.
3. **Фотореалистичное/градиентное**: только трейс (`scripts/smoothmin.py`), смириться с точками.

### Пайплайн «шрифт → чистые глифы» (для надписей)
1. `scripts/font2svg.py` — контуры глифов ПРЯМО из TTF через fontTools (SVGPathPen+TransformPen,
   y-флип `scale(s,-s)`) — без реестра шрифтов Windows вообще. Не тратить время на установку
   шрифтов в систему: HKCU-реестр+кэш обновляются непредсказуемо (logoff, AddFontResourceEx
   лочит файл — при «Device or busy» ставить под НОВЫМ именем; instancer из VF надо ручками
   чинить name ID1/16 на обеих платформах). Кандидаты для Cyrillic-гротесков: Rubik Black,
   Golos Text Black, Unbounded, Montserrat ExtraBold (качать VF из google/fonts + fontTools instancer).
2. Сверка с эталоном — IoU по классам цвета (скелет: зелёный/тёмный маски, 2-прогон: coarse
   сетка размеров/трекинга/базы → fine ±). IoU <0.9 по обеим строкам при всех кандидатах =
   логотип самописный → дальше ручной этап.
3. Ручной этап (пользователь в Inkscape или агент): подгонка точек поверх trace-подложки
   красным слоем. Дальше — доработка кодом: `scripts/build_final.py` (паттерны:
   - полигон → скругление углов дугами: t=r/tan(θ/2), clamp 0.45×ребра, sweep по знаку cross;
   - дефис/капсулы строить ЯВНО 4 дугами, не «M V h v z» (теардроп-баг);
   - относительные субпути требуют ПОЛНОГО pen-state парсера: z→start, m после z = start+offset
     (naive split по (?=[Mm]) ломает координаты; sx,sy = НАЧАЛО субпути, не последняя точка)).
4. Градиенты: «в каждой букве» = objectBoundingBox (дефолт), «на строку» = userSpaceOnUse.
   «Светлый к трети ширины» = stop offset 0.32; «продлить вдвое» = 0.64. Направление — осями x1..y2.
5. Финиш-контроль НЕ глазом, а: пиксельные пробы в опорных точках + IoU + кропы 8x/16x на стыках.
   Ловушка IoU: сравнивай растры одного разрешения. Низкоразрешённый эталон (192px) наивным
   умножением координат (x*4) даёт разреженную маску и ложные 0.1 — надо разрастать пиксели
   в блоки f×f (или рендерить оба в один размер).

### Рабочие принципы (из итераций пользователя)
- Варианты делать ДОБАВЛЕНИЕМ новых файлов (`*.v2.svg`, `*.v3.svg`...), базу не трогать;
  промоушн понравившегося — только отдельным явным словом пользователя.
- «Кажется слабее/сильнее градиент» проверять пиксельными пробами: в этом проекте «первый
  мощный градиент» оказался байт-идентичным текущему — разницу делала толщина букв.
- Упрощение (DP-допуск) жрёт характерные детали (раздвоение 'т', шейки 'И') — IoU-падение
  >0.02 на строке сигналит «слишком порезали», не «шум».

## Как рисовать (recipe)

1. Задумай документ как SVG-текст: примитивы/пути, слои (`inkscape_layers`), градиенты
   (`create_gradient`), фильтры (`apply_filter`), анимации (`inkscape_animation`, SMIL-пресеты).
2. Пиши/правь .svg напрямую (это текст!) — это надёжнее `create_object`.
3. Прогони через сервер: `inkscape_render export_preview` → Read полученного PNG → смотри глазами → правь.
4. Финальные форматы: `inkscape_file convert` (pdf/png/eps/dxf), `inkscape_validation validate`.
5. LPE: `list_lpes` → `apply_lpe` (bend/roughen/envelope/spiro/powerstroke) — специфика Inkscape,
   после него экспорт лучше делать с `--export-plain-svg`-настройкой или конвертом.

## Прямой stdio-тест (когда тулов нет в сессии)

```bash
cd C:/dev/tools/inkscape-mcp && uv run --no-project python -I - <<'EOF'
import asyncio, json
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
async def main():
    t = StdioTransport("uv", ["--directory", "C:/dev/tools/inkscape-mcp", "run", "inkscape-mcp", "--mode", "stdio"])
    async with Client(t) as c:
        print([x.name for x in await c.list_tools()])
        r = await c.call_tool("inkscape_system", {"operation": "status"})
        print(r.content[0].text[:500])
asyncio.run(main())
EOF
```

## Перенос на другую машину

Скопируй папку навыка (`~/.claude/skills/inkscape-mcp`) и `~/.claude.json`
(строка mcpServers.inkscape), затем на новой машине: поставь Inkscape 1.2+ и uv,
запусти `scripts/setup.ps1` — он повторит clone→check→install→add. Пути в конфиге
должны совпадать с фактической папкой клона (setup.ps1 перепишет `claude mcp add` под себя).
