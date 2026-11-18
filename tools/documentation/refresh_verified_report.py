"""Refresh the existing stage report from completed acceptance evidence."""
from pathlib import Path
from copy import deepcopy
import shutil
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
root=Path(__file__).resolve().parents[2]
for file in ('compose-check.json','resilience-check.json','ui-polish-check.json','backup-restore-check.json','ui-outage-check.json'):
 assert (root/'docs/coursework/stages/stage12-summary'/file).exists(),file
path=next(root.glob('Звіт*.docx'));backup=root/'artifacts/report-work/pre-polish-report.docx'
if not backup.exists():shutil.copy2(path,backup)
d=Document(path)
replacements={
'Знімки рисунків 5 і 6 отримано': 'Знімки рисунків 5 і 6 отримано з реального Docker Compose стенда без підміни HTTP-відповідей. Повний корпус завантажено через PostgreSQL outbox і RabbitMQ до MongoDB. У картці документа виділено підсумок матчу та окремі записи статистики; оригінальний текст і технічні дані доступні у розгортних секціях. Додано українські повідомлення про помилки, скидання фільтрів і пагінацію історії імпорту.',
'Рисунок 5 –': 'Рисунок 5 – Корпус документів на Docker Compose стенді',
'Рисунок 6 –': 'Рисунок 6 – Картка документа з підсумком і статистикою',
'Локально пройдено 35 тестів': 'Пройдено 35 архітектурних, прикладних і repository-тестів із реальними контейнерними PostgreSQL і MongoDB. Повний інтеграційний тест імпорту, повторного завантаження, паузи, зміни темпу та перезапусків також пройдено. Production-збірка React / TypeScript успішна.',
'У тимчасовий одноучасниковий MongoDB': 'Повний потік CSV → JSONL → PostgreSQL outbox → RabbitMQ → MongoDB → API → UI зберіг 20 675 документів. Один рядок CSV відхилено через відсутню команду. Повторний імпорт дав 0 нових документів і 20 675 дублікатів. Повторна доставка пакетів та підтверджень не змінила кількість документів або прогрес. Фактичний countDocuments дорівнює транзакційному лічильнику.',
'Повний контейнерний сценарій RabbitMQ/Compose не перевірено': '18 листопада 2026 року додаткові перевірки відмов виконано на окремому Compose стенді з ізольованими томами та тестовим піднабором із 1 000 документів. Пройдено примусове завершення обох workers сигналом SIGKILL, відключення RabbitMQ, конкурентні імпорти, конкурентне створення з одним ключем ідемпотентності та конфлікт двох команд паузи. Пошкоджені повідомлення після п’яти спроб потрапляють до черги помилок. Повторне передавання відкладеного підтвердження відновлює контрольну точку.',
'Відтворюваний запуск, команди перевірки': 'На реальних відключеннях MongoDB і PostgreSQL перевірено HTTP 503, українські повідомлення UI та відновлення після запуску БД. Резервні копії основного стенда відновлено в окремі тестові БД: 20 675 документів, узгоджений лічильник і 3 завершені завдання імпорту. Основні БД не перезаписувались. Відтворювані сценарії та JSON-докази наведено у tools, README.md і stage12-summary.'
}
for p in d.paragraphs:
 for prefix,value in replacements.items():
  if p.text.startswith(prefix):
   # Preserve paragraph style and first-run formatting.
   props=deepcopy(p.runs[0]._r.rPr) if p.runs and p.runs[0]._r.rPr is not None else None
   p.clear();r=p.add_run(value)
   if props is not None:r._r.insert(0,props)
   break
for i,p in enumerate(d.paragraphs):
 if p.text.startswith('Рисунок 5 –') or p.text.startswith('Рисунок 6 –'):
  picture=d.paragraphs[i-1];picture.clear();picture.paragraph_format.keep_with_next=True
  name='ui-corpus.png' if p.text.startswith('Рисунок 5') else 'ui-document.png'
  picture.add_run().add_picture(str(root/'docs/coursework/stages/stage12-summary'/name),width=Inches(5.8));picture.alignment=WD_ALIGN_PARAGRAPH.CENTER
if not any(p.text.startswith('Аудит UI виконано') for p in d.paragraphs):
 p=d.add_paragraph('Аудит UI виконано у Chrome та Edge: відкриття й закриття документа, повернення фокуса, мобільне прокручування, помилковий токен, цілі значення темпу, фільтри та пагінація. Автоматична перевірка axe-core за WCAG 2 A/AA і 2.1 AA не виявила порушень у перевірених станах; це не замінює повного аудиту зі скринридером. Переформатування тексту перевірено на всіх 20 675 документах: зміст збережено, оригінальний текст залишається доступним.')
 p=d.add_paragraph('Один вузол MongoDB і один RabbitMQ не є відмовостійким кластером. Значення темпу є цільовим, а не гарантією продуктивності; навантажувальне дослідження та перевірку фізичних мобільних пристроїв не заявлено. Шардування, партиціювання, Elasticsearch, Redis і Neo4j залишаються наступними етапами.')
# Keep appended result paragraphs consistent with the existing report.
ref=next(p for p in d.paragraphs if p.text.startswith('Пройдено 35'))
for p in d.paragraphs:
 if p.text.startswith(('Аудит UI виконано','Один вузол MongoDB і один RabbitMQ')):
  if p._p.pPr is not None:p._p.remove(p._p.pPr)
  p._p.insert(0,deepcopy(ref._p.pPr))
d.save(path)
print(path)
