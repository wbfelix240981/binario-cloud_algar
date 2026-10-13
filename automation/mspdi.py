"""Gera um XML do Microsoft Project (MSPDI) a partir dos marcos do painel da Algar.
Uso: python3 mspdi.py metas.json saida.xml"""
import json, sys, datetime as dt
from xml.sax.saxutils import escape

metas = json.load(open(sys.argv[1]))
out = sys.argv[2]

FERIADOS = {dt.date(2026, 10, 12), dt.date(2026, 11, 2), dt.date(2026, 11, 15), dt.date(2026, 11, 20)}
PESO = {'backlog': 0, 'in planning': 10, 'in progress': 50, 'in review': 75, 'in test': 75, 'blocked': 0, 'waiting': 25, 'shipped': 100}
STATUS = {'backlog': 'Não iniciado', 'in planning': 'Planejamento', 'in progress': 'Em andamento',
          'in review': 'Em revisão', 'in test': 'Em teste', 'blocked': 'Bloqueada', 'waiting': 'Aguardando retorno', 'shipped': 'Concluído'}
PARTE = {'binario': ['Binário Cloud'], 'algar': ['Algar'], 'ambos': ['Binário Cloud', 'Algar']}
PARTE_TXT = {'binario': 'Binário', 'algar': 'Algar', 'ambos': 'Binário + Algar', 'nd': 'A definir'}

def d(s): return dt.date.fromisoformat(s[:10])
def util(x): return x.weekday() < 5 and x not in FERIADOS
def ajusta_inicio(x):
    while not util(x): x += dt.timedelta(days=1)
    return x
def ajusta_fim(x):
    while not util(x): x -= dt.timedelta(days=1)
    return x
def dias_uteis(a, b):
    n, x = 0, a
    while x <= b:
        n += util(x); x += dt.timedelta(days=1)
    return max(n, 1)
def iso_ini(x): return f"{x.isoformat()}T08:00:00"
def iso_fim(x): return f"{x.isoformat()}T17:00:00"
def dur(n): return f"PT{n*8}H0M0S"

tarefas, uid = [], 0
recursos = {'Binário Cloud': 1, 'Algar': 2}
atribs = []

def add(**k):
    global uid
    uid += 1; k['uid'] = uid; tarefas.append(k); return uid

proj_ini = proj_fim = None
for mi, m in enumerate(metas, start=1):
    if m.get('internal') or m['num'] == 999: continue
    fases = [dict(f) for f in m['fases'] if not f.get('oculto')]
    if not fases:   # marco sem atividades: entra como tarefa única com as datas do próprio marco
        if not m.get('due'): continue
        fases = [{'n': m['name'], 'party': 'nd', 'status': m.get('status', 'backlog'), 'start': m.get('start') or m['due'], 'due': m['due'], 'sem_data': False}]
    for f in fases:  # sem datas no ClickUp: usa as datas do marco (ou do projeto)
        if not f.get('due'): f['due'] = m.get('due') or '2026-10-30'; f['sem_data'] = True
        if not f.get('start'): f['start'] = m.get('start') or f['due']
    base = [f for f in fases if not f.get('origem')]
    extra = sorted([f for f in fases if f.get('origem')], key=lambda f: (f.get('start') or f['due'], f['due']))
    ordem = base + extra
    ini = min(ajusta_inicio(d(f.get('start') or f['due'])) for f in fases)
    fim = max(ajusta_fim(d(f['due'])) for f in fases)
    proj_ini = min(proj_ini or ini, ini); proj_fim = max(proj_fim or fim, fim)
    pct = round(sum(PESO.get(f['status'], 0) for f in fases) / len(fases))
    nota = m.get('detail', '')
    if m.get('entregavel'): nota += f"\nEntregável da proposta: {m['entregavel']}"
    add(nome=m['name'], nivel=1, outline=str(len([t for t in tarefas if t['nivel'] == 1]) + 1), resumo=True,
        ini=ini, fim=fim, pct=pct, nota=nota, partes=[])
    n1 = tarefas[-1]['outline']
    for k, f in enumerate(ordem, start=1):
        a = ajusta_inicio(d(f.get('start') or f['due'])); b = ajusta_fim(d(f['due']))
        if b < a: b = a
        nota = [f"Responsável: {PARTE_TXT.get(f['party'], f['party'])}" + (f" · {f['assignee']}" if f.get('assignee') else ''),
                f"Status no painel: {STATUS.get(f['status'], f['status'])}"]
        if f.get('origem'): nota.append(f"Origem: {f['origem']}")
        else: nota.append("Origem: atividade definida no planejamento")
        if f.get('sem_data'): nota.append("Sem datas no ClickUp: usadas as datas do marco")
        if f.get('obs'): nota.append(f"Comentário: {f['obs']}")
        t = add(nome=f['n'], nivel=2, outline=f"{n1}.{k}", resumo=False, ini=a, fim=b,
                pct=PESO.get(f['status'], 0), nota="\n".join(nota), partes=PARTE.get(f['party'], []),
                texto1=PARTE_TXT.get(f['party'], ''), texto2=f.get('assignee', ''), texto3=STATUS.get(f['status'], ''))
        for r in PARTE.get(f['party'], []):
            atribs.append((t, recursos[r], a, b))

hoje = dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
X = []
w = X.append
w('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
w('<Project xmlns="http://schemas.microsoft.com/project">')
w('<SaveVersion>14</SaveVersion>')
w('<Name>Projeto Algar - BCAPI BC Billing</Name>')
w('<Title>Projeto Algar · BCAPI | BC Billing</Title>')
w('<Company>Binário Cloud</Company><Author>Wagner Bento Felix</Author>')
w(f'<CreationDate>{hoje}</CreationDate><LastSaved>{hoje}</LastSaved>')
w('<ScheduleFromStart>1</ScheduleFromStart>')
w(f'<StartDate>{iso_ini(proj_ini)}</StartDate><FinishDate>{iso_fim(proj_fim)}</FinishDate>')
w('<CalendarUID>1</CalendarUID><DefaultStartTime>08:00:00</DefaultStartTime><DefaultFinishTime>17:00:00</DefaultFinishTime>')
w('<MinutesPerDay>480</MinutesPerDay><MinutesPerWeek>2400</MinutesPerWeek><DaysPerMonth>20</DaysPerMonth>')
w('<DurationFormat>7</DurationFormat><WorkFormat>2</WorkFormat><NewTaskStartDate>0</NewTaskStartDate>')
w('<CurrencySymbol>R$</CurrencySymbol><CurrencyCode>BRL</CurrencyCode><WeekStartDay>1</WeekStartDay>')
w('<ExtendedAttributes>')
for fid, alias in [('188743731', 'Responsável (empresa)'), ('188743734', 'Responsável (pessoa)'), ('188743737', 'Status no painel')]:
    w(f'<ExtendedAttribute><FieldID>{fid}</FieldID><FieldName>Text{["188743731","188743734","188743737"].index(fid)+1}</FieldName><Alias>{escape(alias)}</Alias></ExtendedAttribute>')
w('</ExtendedAttributes>')
# calendário: seg-sex 8-12 / 13-17, com feriados
w('<Calendars><Calendar><UID>1</UID><Name>Padrão Brasil</Name><IsBaseCalendar>1</IsBaseCalendar><WeekDays>')
for day in range(1, 8):
    if day in (1, 7):
        w(f'<WeekDay><DayType>{day}</DayType><DayWorking>0</DayWorking></WeekDay>')
    else:
        w(f'<WeekDay><DayType>{day}</DayType><DayWorking>1</DayWorking><WorkingTimes>'
          '<WorkingTime><FromTime>08:00:00</FromTime><ToTime>12:00:00</ToTime></WorkingTime>'
          '<WorkingTime><FromTime>13:00:00</FromTime><ToTime>17:00:00</ToTime></WorkingTime></WorkingTimes></WeekDay>')
for f in sorted(FERIADOS):
    w(f'<WeekDay><DayType>0</DayType><DayWorking>0</DayWorking><TimePeriod><FromDate>{f}T00:00:00</FromDate><ToDate>{f}T23:59:00</ToDate></TimePeriod></WeekDay>')
w('</WeekDays></Calendar></Calendars>')

w('<Tasks>')
w(f'<Task><UID>0</UID><ID>0</ID><Name>Projeto Algar · BCAPI | BC Billing</Name><OutlineLevel>0</OutlineLevel><OutlineNumber>0</OutlineNumber><Summary>1</Summary>'
  f'<Start>{iso_ini(proj_ini)}</Start><Finish>{iso_fim(proj_fim)}</Finish></Task>')
for i, t in enumerate(tarefas, start=1):
    n = dias_uteis(t['ini'], t['fim'])
    w('<Task>')
    w(f"<UID>{t['uid']}</UID><ID>{i}</ID><Name>{escape(t['nome'])}</Name><Type>1</Type>")
    w(f"<OutlineNumber>{t['outline']}</OutlineNumber><OutlineLevel>{t['nivel']}</OutlineLevel>")
    w(f"<Start>{iso_ini(t['ini'])}</Start><Finish>{iso_fim(t['fim'])}</Finish>")
    w(f"<Duration>{dur(n)}</Duration><DurationFormat>7</DurationFormat>")
    w(f"<Summary>{1 if t['resumo'] else 0}</Summary><Milestone>0</Milestone><Manual>0</Manual>")
    w(f"<PercentComplete>{t['pct']}</PercentComplete>")
    if not t['resumo']:
        w(f"<ConstraintType>4</ConstraintType><ConstraintDate>{iso_ini(t['ini'])}</ConstraintDate>")
        if t['pct'] > 0: w(f"<ActualStart>{iso_ini(t['ini'])}</ActualStart>")
        if t['pct'] == 100: w(f"<ActualFinish>{iso_fim(t['fim'])}</ActualFinish>")
        for fid, key in [('188743731', 'texto1'), ('188743734', 'texto2'), ('188743737', 'texto3')]:
            if t.get(key): w(f"<ExtendedAttribute><FieldID>{fid}</FieldID><Value>{escape(t[key])}</Value></ExtendedAttribute>")
    w(f"<Notes>{escape(t['nota'])}</Notes>")
    w('</Task>')
w('</Tasks>')

w('<Resources><Resource><UID>0</UID><ID>0</ID><Name>Não atribuído</Name><Type>1</Type></Resource>')
for nome, rid in recursos.items():
    w(f'<Resource><UID>{rid}</UID><ID>{rid}</ID><Name>{escape(nome)}</Name><Type>1</Type><MaxUnits>1</MaxUnits><CalendarUID>1</CalendarUID></Resource>')
w('</Resources>')
w('<Assignments>')
for k, (t, r, a, b) in enumerate(atribs, start=1):
    n = dias_uteis(a, b)
    w(f'<Assignment><UID>{k}</UID><TaskUID>{t}</TaskUID><ResourceUID>{r}</ResourceUID><Units>1</Units>'
      f'<Start>{iso_ini(a)}</Start><Finish>{iso_fim(b)}</Finish><Work>{dur(n)}</Work></Assignment>')
w('</Assignments>')
w('</Project>')
open(out, 'w', encoding='utf-8').write("\n".join(X))
print(f"{len(tarefas)} tarefas ({sum(t['nivel']==1 for t in tarefas)} marcos), {len(atribs)} atribuições, {proj_ini} → {proj_fim}")
