"""Small password-protected browser interface for running historical backtests."""
from __future__ import annotations

import hmac
import os
from datetime import date
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from api_client import api_request
from server import mcp
from tools.backtesting import run_walk_forward_backtest


_PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MyAnalytics — проверка модели</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#10151d;color:#e8edf5;font:16px system-ui,sans-serif}
main{max-width:760px;margin:36px auto;padding:24px}h1{font-size:26px;margin:0 0 8px}p{color:#aeb9c8;line-height:1.5}
form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;background:#192230;padding:20px;border-radius:14px}
label{display:grid;gap:6px;color:#bac6d6;font-size:14px}input{width:100%;padding:11px;border:1px solid #39485c;border-radius:8px;background:#101923;color:#fff;font:inherit}
.wide{grid-column:1/-1}button{padding:13px;border:0;border-radius:8px;background:#4d86e8;color:white;font-weight:700;font-size:16px;cursor:pointer}
button:disabled{opacity:.55;cursor:wait}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0b1119;border:1px solid #293648;border-radius:10px;padding:16px;min-height:80px;color:#dbe7f8}
small{color:#8e9bad}.warning{color:#f2c879}
@media(max-width:560px){main{margin:12px auto;padding:16px}form{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
</head>
<body><main>
<h1>MyAnalytics Football — тест модели</h1>
<p>Запуск хронологического walk-forward бэктеста. Для каждого матча прогноз строится только по более ранним результатам. Запросы расходуют дневную квоту API-Football.</p>
<form id="run">
<label class="wide">Код доступа<input id="token" type="password" autocomplete="current-password" required placeholder="Вставь код доступа"></label>
<label>ID лиги<input id="league" type="number" min="1" value="140" required></label>
<label>Сезон<input id="season" type="number" min="2000" max="2100" value="2026" required></label>
<label>Начало периода<input id="from" type="date" value="2026-07-01" required></label>
<label>Конец периода<input id="to" type="date" value="2026-11-08" required></label>
<label>Минимум предыдущих матчей<input id="history" type="number" min="1" max="10" value="5" required></label>
<button class="wide" id="submit" type="submit">Запустить бэктест</button>
</form>
<p class="warning">Результаты оценивают качество вероятностей, а не доходность ставок. Без исторических коэффициентов ROI не рассчитывается.</p>
<h2>Результат</h2><pre id="result">Заполни параметры и нажми «Запустить бэктест».</pre>
<small>Ключ API-Football хранится только на сервере. Код доступа не сохраняется в браузере.</small>
</main>
<script>
const form=document.getElementById('run'),btn=document.getElementById('submit'),out=document.getElementById('result');
form.addEventListener('submit',async e=>{
 e.preventDefault();btn.disabled=true;btn.textContent='Выполняется…';out.textContent='Получаю матчи и рассчитываю метрики…';
 const payload={league_id:Number(document.getElementById('league').value),season:Number(document.getElementById('season').value),from_date:document.getElementById('from').value,to_date:document.getElementById('to').value,min_history:Number(document.getElementById('history').value)};
 try{
  const response=await fetch('/api/backtest',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+document.getElementById('token').value},body:JSON.stringify(payload)});
  const data=await response.json();out.textContent=JSON.stringify(data,null,2);
 }catch(err){out.textContent='Ошибка соединения: '+err.message}
 finally{btn.disabled=false;btn.textContent='Запустить бэктест';}
});
</script></body></html>"""


def _unauthorized() -> JSONResponse:
    return JSONResponse({"success": False, "error": "Invalid or missing dashboard access code."}, status_code=401)


@mcp.custom_route("/tester", methods=["GET"], include_in_schema=False)
async def backtest_page(request: Request) -> HTMLResponse:
    return HTMLResponse(_PAGE, headers={"Cache-Control": "no-store"})


@mcp.custom_route("/api/backtest", methods=["POST"], include_in_schema=False)
async def run_backtest_route(request: Request) -> JSONResponse:
    expected = os.getenv("ANALYTICS_DASHBOARD_TOKEN", "")
    supplied = request.headers.get("authorization", "")
    if not expected or not supplied.startswith("Bearer ") or not hmac.compare_digest(
        supplied[7:], expected
    ):
        return _unauthorized()

    try:
        if int(request.headers.get("content-length", "0") or "0") > 16_384:
            return JSONResponse({"success": False, "error": "Request body too large."}, status_code=413)
        payload: dict[str, Any] = await request.json()
        league_id = int(payload.get("league_id", 0))
        season = int(payload.get("season", 0))
        min_history = int(payload.get("min_history", 5))
        start = date.fromisoformat(str(payload.get("from_date", "")))
        end = date.fromisoformat(str(payload.get("to_date", "")))
        span = (end - start).days
        if league_id < 1 or season < 2000 or season > 2100:
            raise ValueError("Укажи корректные ID лиги и год сезона.")
        if span < 0 or span > 180:
            raise ValueError("Период должен быть хронологическим и не длиннее 180 дней.")
        if min_history < 1 or min_history > 10:
            raise ValueError("Минимум предыдущих матчей должен быть от 1 до 10.")
    except (ValueError, TypeError, KeyError) as exc:
        return JSONResponse({"success": False, "error": str(exc) or "Некорректные параметры."}, status_code=400)
    except Exception:
        return JSONResponse({"success": False, "error": "Не удалось прочитать параметры запроса."}, status_code=400)

    result = await api_request("/fixtures", {
        "league": league_id,
        "season": season,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "status": "FT-AET-PEN",
    })
    if not result.get("success"):
        return JSONResponse(result, status_code=502)

    report = run_walk_forward_backtest(result.get("data") or [], min_history=min_history)
    report["league_id"] = league_id
    report["season"] = season
    report["date_range"] = {"from": start.isoformat(), "to": end.isoformat()}
    report["rate_limit_remaining"] = result.get("rate_limit_remaining")
    return JSONResponse(report, headers={"Cache-Control": "no-store"})
