"""Update the existing Ukrainian coursework report, retaining original sections and anchors.
Run using the bundled document runtime; render and inspect the result afterwards.
"""
from pathlib import Path
from copy import deepcopy
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

root=Path(__file__).resolve().parents[2]
path=next(root.glob('Звіт*.docx'))
doc=Document(path)
if any(p.text.startswith('10 ВИБІР КОНКРЕТНИХ') for p in doc.paragraphs):
    raise SystemExit('Stage report already updated; review manually before rerunning')

def replace_text(p,text):
    nodes=p._p.xpath('.//w:t')
    if nodes:
        nodes[0].text=text
        for node in nodes[1:]:node.text=''
    else:p.add_run(text)

# Existing report diagrams: target architecture, current classes, current document flow.
images=[p for p in doc.paragraphs if p._p.xpath('.//w:drawing')]
for p,name in zip(images,['target-modules','stage5-class-architecture','document-flow']):
    for run in list(p._p.findall(qn('w:r'))):p._p.remove(run)
    p.add_run().add_picture(str(root/'docs/diagrams/images'/f'{name}.png'),width=Inches(6.0))
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next=True

replacements={
 'Рисунок 1 – Огляд взаємодії модулів':'Рисунок 1 – Цільова архітектура наступних етапів',
 'Рис. 2 Архітектурна схема зв’язків класів та модулів (Станом на: 03.10.2026)':'Рисунок 2 – Реалізовані класи та порти етапів 9–12',
 'Рис. 3 Фінальна схема взаємодії елементів розподіленої системи (Станом на: 03.10.2026))':'Рисунок 3 – Запис і читання текстового корпусу на етапах 9–12',
 '6.3 Топологія та стратегія шардінгу NoSQL-сховища MongoDB':'6.3 Цільова топологія MongoDB для наступних етапів',
 '6.4 Механізм нормалізації ключів та стратегія кешування Redis':'6.4 Запланована нормалізація пошуку та кешування Redis',
}
for p in doc.paragraphs:
    if p.text in replacements:replace_text(p,replacements[p.text])
    if p.text.startswith('Повнорозмірна схема: docs/diagrams/images/modules.svg'):
        replace_text(p,'Цільова схема збережена у docs/diagrams/target-modules.mmd та docs/diagrams/images/target-modules.png. Поточний стенд етапів 9–12 наведено в розділі 10; пошук Elasticsearch, кеш Redis, граф Neo4j і шардування відкладено.')
    if p.text.startswith('Загальну взаємодію клієнтських вебінтерфейсів, конвеєра імпорту'):
        replace_text(p,'Рисунок 3 відображає реалізований шлях текстового корпусу через Ingestion, RabbitMQ, Content і MongoDB. Опис повнотекстового пошуку та похідних проєкцій нижче належить до цільової архітектури наступних етапів.')

heading4=next(p for p in doc.paragraphs if p.text=='4 АРХІТЕКТУРА СИСТЕМИ')
notice=heading4.insert_paragraph_before('Уточнення стану реалізації. Розділи 4–9 зберігають архітектурні рішення та результати попередніх етапів. На етапах 9–12 реалізовано один вузол MongoDB, PostgreSQL для імпорту та RabbitMQ. Шардування, партиціювання, Elasticsearch, Redis і Neo4j залишено наступним етапам. Поточну реалізацію та перевірки описано в розділах 10–13.')
notice.paragraph_format.space_after=Pt(10)
anchor=next(p for p in doc.paragraphs if p.style.name=='Heading 1' and p.text.startswith('10 РЕЗУЛЬТАТИ'))
# Replace obsolete summary text while retaining the original heading bookmark.
for p in list(doc.paragraphs)[next(i for i,p in enumerate(doc.paragraphs) if p._p is anchor._p)+1:]:
    p._element.getparent().remove(p._element)
replace_text(anchor,'13 РЕЗУЛЬТАТИ ПОТОЧНОГО ЕТАПУ')
anchor.paragraph_format.page_break_before=True


def paragraph(text,style=None):
    p=anchor.insert_paragraph_before(text,style)
    p.paragraph_format.space_after=Pt(6)
    return p

def heading(text,level=1):
    p=paragraph(text,'Heading '+str(level))
    for run in p.runs:run.font.color.rgb=RGBColor(0,0,0)
    p.paragraph_format.keep_with_next=True
    if level==1:p.paragraph_format.page_break_before=True
    return p

def picture(filename,caption,width=6.0):
    p=paragraph('');p.add_run().add_picture(str(root/filename),width=Inches(width))
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True
    p=paragraph(caption);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:run.font.size=Pt(10)

def table(headers,rows):
    t=doc.add_table(rows=1,cols=len(headers));t.style='Table Grid';t.alignment=WD_TABLE_ALIGNMENT.CENTER
    for c,text in zip(t.rows[0].cells,headers):c.text=text
    for values in rows:
        for c,text in zip(t.add_row().cells,values):c.text=text
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after=Pt(4)
                for r in p.runs:r.font.size=Pt(10)
    for c in t.rows[0].cells:
        for r in c.paragraphs[0].runs:r.bold=True
    anchor._p.addprevious(t._tbl)

heading('10 ВИБІР КОНКРЕТНИХ СИСТЕМ КЕРУВАННЯ БАЗАМИ ДАНИХ')
paragraph('Основною базою даних для етапів 10–12 обрано MongoDB. Вона зберігає найбільший набір прикладних даних поточного зрізу — англомовні текстові документи про матчі та карти Counter-Strike. PostgreSQL використано для транзакційного стану завдань імпорту. Вибір спирається на аналіз розділів 8 і 9; нижче зафіксовано саме межі поточної реалізації.')
paragraph('Таблиця 10.1 – Призначення СУБД і стан реалізації')
table(['Технологія','Призначення','Етапи 9–12'],[
 ['MongoDB','Текстовий корпус і метадані','Реалізовано один вузол'],
 ['PostgreSQL','Стан, пакети та прогрес імпорту','Реалізовано'],
 ['Elasticsearch','Повнотекстовий індекс','Наступні етапи'],
 ['Redis','Кеш результатів','Наступні етапи'],
 ['Neo4j','Граф зв’язків','Наступні етапи']])
paragraph('RabbitMQ є брокером повідомлень, а не базою даних. MongoDB налаштовано як одноучасниковий replica set лише для транзакцій. Немає шардування, партиціювання, mongos, конфігураційних серверів або додаткових реплік. Такий стенд не забезпечує failover.')
picture('docs/diagrams/images/modules.png','Рисунок 4 – Поточний стенд етапів 9–12',width=4.7)

heading('11 ПІДГОТОВКА КОРПУСУ ТА РЕАЛІЗАЦІЯ ЗАПИТІВ')
heading('11.1 Дані та походження',2)
paragraph('Використано тільки файл cs2_all_tiers_games.csv із локального архіву. Початковий набір містить 20 676 рядків: 9 923 підсумки матчів і 10 753 результати карт. Після валідації підготовлено 20 675 документів; рядок CSV 20100 відхилено через відсутність team1. Tier-файли не імпортуються повторно.')
paragraph('Тексти формуються англомовними шаблонами без LLM. Опис містить лише наявні назви команд, турнір, дату, рахунок, карту й статистику. Пропуски не замінюються вигаданими значеннями. Ідентифікатор UUIDv5 залежить від джерела та ключа match_id:series або match_id:map:game_id. Тому повторний імпорт незмінного знімка не створює нових документів.')
paragraph('Кожен документ містить title, text, language, provider, source_id, source_url, corpus_scope, publication_status та metadata. Метадані зберігають тип документа, команди, турнір, дату, SHA-256 вихідного CSV і версію шаблону. Часовий пояс вихідної дати невідомий і не домислюється. Непідтверджені посилання на внутрішні сутності Competition залишаються порожніми.')
heading('11.2 Запис і відновлення',2)
paragraph('Ingestion створює завдання у власній PostgreSQL. Worker атомарно записує пакет, контрольну позицію виробника та outbox, після чого диспетчер публікує команду в RabbitMQ з підтвердженням. Content зберігає документи, квитанцію пакета, лічильник і вихідне повідомлення в одній MongoDB-транзакції. ACK надсилається після збереження.')
paragraph('Завершення пакета оновлює PostgreSQL-прогрес лише один раз. Контрольна точка враховує неперервно завершені пакети, навіть якщо підтвердження надійшли не за порядком. Повторна доставка того самого пакета повертає його попередній результат; нове завдання для тих самих документів рахує дублікати. Після п’яти невдалих спроб повідомлення переходить до черги помилок.')
paragraph('Темп задається в документах за секунду: початково 100, допустимо 10–5000. Це бажаний темп, а не гарантована пропускна здатність. Пауза припиняє нове виробництво, але дозволяє завершити вже відправлені пакети. Показники спроб, підтверджених нових записів, дублікатів, відхилень і backlog розділені.')
heading('11.3 Запити на читання і пошук',2)
paragraph('MongoDB виконує читання за UUID, список із пагінацією, фільтри типу документа, точної назви команди чи турніру та діапазону дат. Пошук q є буквальним фрагментом заголовка або тексту без урахування регістру. Спеціальні символи екрануються; довжину обмежено 200 символами, час MongoDB-запиту — двома секундами. Ранжування та морфологію відкладено.')
paragraph('Для запису застосовано update_one із $setOnInsert, для вибірок — find_one, find і count_documents, для швидкості — aggregate за індексованим часом завершення пакетів. Лічильник корпусу оновлюється в транзакції; повне сканування щосекунди не виконується. SQL-запити PostgreSQL використовують параметри asyncpg, блокування рядків та ON CONFLICT для ідемпотентності.')
paragraph('Повний каталог реалізованих запитів із параметрами, індексами та прикладами міститься у docs/stages9-12-queries.md. Підготовлений зразок документа і контрольні суми збережено у stage10-11-summary. Зміна знімка чи шаблону для вже відомого ID потребує окремої міграції.')

heading('12 ІНТЕРФЕЙС І НАСКРІЗНИЙ ПОТІК ДАНИХ')
paragraph('Frontend реалізовано на React, TypeScript і Vite з українським інтерфейсом. Екран корпусу містить пошук, фільтри та пагінацію; картка відкриває повний текст і походження. Операторський екран керує імпортом, темпом, паузою та продовженням і оновлює показники приблизно щосекунди.')
paragraph('Повний шлях читання: UI → FastAPI → CorpusController → CorpusQueryService → CorpusStore / MongoCorpusRepository → MongoDB та назад. GET /api/v1/documents повертає список, GET /api/v1/documents/{id} — документ, GET /api/v1/corpus/statistics — показники. За замовчуванням сторінка містить 20 записів, максимум — 100.')
paragraph('Операції /api/v1/replays захищено bearer-токеном оператора. Він вводиться користувачем і зберігається лише в пам’яті UI. POST створює завдання з відповіддю 202; PATCH /rate змінює темп, POST /pause і /resume керують станом. Джерело обирається із серверного каталогу, довільний файловий шлях не приймається. Передбачено відповіді 401, 404, 409, 422 та 503.')
picture('docs/coursework/stages/stage12-summary/ui-corpus.png','Рисунок 5 – Корпус у UI з даними справжньої локальної MongoDB')
picture('docs/coursework/stages/stage12-summary/ui-document.png','Рисунок 6 – Повний документ і метадані через Content API')
paragraph('Знімки рисунків 5 і 6 отримано без підміни HTTP-відповідей. У цій перевірці дані попередньо завантажено через command service без RabbitMQ. Операторські дії та mobile-адаптацію окремо перевірено Playwright із явно заданими тестовими відповідями; такі перевірки не прирівнюються до тесту брокера.')

# New current summary after the preserved original heading anchor.
for text in [
 'Для етапів 9–12 реалізовано підготовку корпусу, збереження MongoDB, стан імпорту PostgreSQL, RabbitMQ-адаптери, API, frontend, Docker Compose та документацію. Шардування, партиціювання, Elasticsearch, Redis і Neo4j у поточному стенді відсутні.',
 'Локально пройдено 35 тестів з увімкненими справжніми PostgreSQL і MongoDB. Перевірено архітектуру, перетворення CSV, валідацію API, транзакції, rollback, ідемпотентність, outbox, переставлені підтвердження та контрольні точки. Production-збірка frontend успішна.',
 'У тимчасовий одноучасниковий MongoDB 7.0.14 через CorpusCommandService записано всі 20 675 підготовлених документів. Фактичну кількість звірено з транзакційним лічильником. Перевірено реальний шлях React → Content API → MongoDB для списку, повного документа й порожнього пошуку.',
 'Повний контейнерний сценарій RabbitMQ/Compose не перевірено: Docker Engine недоступний у середовищі виконання. Підготовлено окремий інтеграційний тест для повторного імпорту, зміни темпу, паузи, перезапуску workers і збереження даних після перезапуску БД. Він пропускається без явного ввімкнення RUN_STACK_TESTS=1. Пропускна здатність і відмовостійкість не заявляються як виміряні результати.',
 'Відтворюваний запуск, команди перевірки та обмеження наведено у README.md; результати етапів — у docs/coursework/stages/stage9-summary, docs/coursework/stages/stage10-11-summary та stage12-summary. Попередні результати контейнерного smoke test PostgreSQL залишаються історичними результатами розділу 7.'
]:doc.add_paragraph(text)

# Mark the existing automatic contents field dirty. Keep all old bookmarks and links.
for field in doc._element.xpath('.//w:fldChar[@w:fldCharType="begin"]'):
    field.set(qn('w:dirty'),'true')
settings=doc.settings.element
update=settings.find(qn('w:updateFields'))
if update is None:update=OxmlElement('w:updateFields');settings.append(update)
update.set(qn('w:val'),'true')
# Update cached old summary entry and insert new stage entries before it.
for p in list(doc.paragraphs):
    if p.style.name.lower().startswith('toc') and p.text.startswith('10 РЕЗУЛЬТАТИ'):
        for title in ['10 ВИБІР КОНКРЕТНИХ СИСТЕМ КЕРУВАННЯ БАЗАМИ ДАНИХ','11 ПІДГОТОВКА КОРПУСУ ТА РЕАЛІЗАЦІЯ ЗАПИТІВ','12 ІНТЕРФЕЙС І НАСКРІЗНИЙ ПОТІК ДАНИХ']:
            p.insert_paragraph_before(title+'\t',p.style)
        replace_text(p,'13 РЕЗУЛЬТАТИ ПОТОЧНОГО ЕТАПУ\t')
# Make newly inserted headings bookmark targets without changing existing identifiers.
for i,p in enumerate(doc.paragraphs):
    if p.style.name.startswith('Heading') and not p._p.xpath('./w:bookmarkStart'):
        start=OxmlElement('w:bookmarkStart');start.set(qn('w:id'),str(10000+i));start.set(qn('w:name'),f'stage_heading_{i}')
        end=OxmlElement('w:bookmarkEnd');end.set(qn('w:id'),str(10000+i))
        p._p.insert(0,start);p._p.append(end)
doc.save(path)
print(path)
