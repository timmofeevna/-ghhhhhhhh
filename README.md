import os
import random
import json
import asyncio
import datetime
import aiohttp
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Временной Хаб", description="Ловушка для остановленного времени")

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("user_data", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

user_behaviour = {
    "visits": [],
    "last_commutation": None,
    "rain_mode": False
}

apartment_map = {
    "walls": [(0, 0), (10, 0), (10, 10), (0, 10)],
    "obstacles": [(2, 2), (7, 7), (4, 8)],
    "vacuum_pos": [5.0, 5.0],
    "vacuum_angle": 0
}

async def get_weather_rain_status():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://wttr.in/Moscow?format=j1") as resp:
                data = await resp.json()
                current_condition = data.get("current_condition", [{}])[0]
                weather_desc = current_condition.get("weatherDesc", [{}])[0].get("value", "").lower()
                is_raining = "rain" in weather_desc or "drizzle" in weather_desc or "shower" in weather_desc
                return is_raining
    except:
        return random.random() < 0.3

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("exam_check.html", {"request": request})

@app.post("/enter")
async def enter_site(data: dict):
    choice = data.get("choice")
    if choice not in ["ещё нет", "забыл"]:
        raise HTTPException(status_code=400, detail="Неверный выбор")
    user_behaviour["visits"].append(datetime.datetime.now().isoformat())
    return {"status": "ok", "redirect": "/hub"}

@app.get("/hub", response_class=HTMLResponse)
async def hub(request: Request):
    is_raining = await get_weather_rain_status()
    user_behaviour["rain_mode"] = is_raining
    
    return templates.TemplateResponse("hub.html", {
        "request": request,
        "rain_mode": is_raining
    })

@app.get("/api/timer")
async def get_timer():
    minutes = random.randint(2, 47)
    return {"seconds": minutes * 60, "minutes": minutes}

@app.get("/api/vacuum_stream")
async def vacuum_stream():
    async def generate():
        while True:
            x, y = apartment_map["vacuum_pos"]
            angle = apartment_map["vacuum_angle"]
            
            # Хаотичное движение с поворотами
            move_choice = random.random()
            if move_choice < 0.7:
                dx = random.uniform(-0.4, 0.4)
                dy = random.uniform(-0.4, 0.4)
                new_x = max(0.3, min(9.7, x + dx))
                new_y = max(0.3, min(9.7, y + dy))
                angle += random.uniform(-0.3, 0.3)
            else:
                new_x, new_y = x, y
                angle += random.uniform(-0.8, 0.8)
            
            apartment_map["vacuum_pos"] = [new_x, new_y]
            apartment_map["vacuum_angle"] = angle % 360
            
            data = {
                "x": new_x,
                "y": new_y,
                "angle": angle,
                "walls": apartment_map["walls"],
                "obstacles": apartment_map["obstacles"]
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(random.uniform(1.0, 2.5))
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/upload_apartment")
async def upload_apartment(data: dict):
    global apartment_map
    if "walls" in data and "obstacles" in data:
        apartment_map["walls"] = data["walls"]
        apartment_map["obstacles"] = data["obstacles"]
        with open("user_data/apartment_map.json", "w") as f:
            json.dump(apartment_map, f)
        return {"status": "ok", "message": "Схема квартиры загружена"}
    else:
        raise HTTPException(status_code=400, detail="Неверный формат схемы")

@app.post("/api/commutate")
async def commutate(request: Request):
    data = await request.json()
    user_behaviour["last_commutation"] = {
        "time": datetime.datetime.now().isoformat(),
        "inputs": data.get("inputs", [])
    }
    with open("user_data/commutations.json", "a") as f:
        f.write(json.dumps(user_behaviour["last_commutation"]) + "\n")
    
    return {"message": "⚡ РЕЗУЛЬТАТ ОТПРАВЛЕН МНЕ ⚡\nСпасибо за участие в сессии."}

@app.get("/api/logs")
async def get_logs():
    logs = [
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🌧️ дождь: {'ДА, ВАЙБ АКТИВЕН' if user_behaviour['rain_mode'] else 'СУХО, ОЖИДАНИЕ'}",
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🌀 пылесос: маршрут скорректирован, столкновений: {random.randint(0, 3)}",
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 📡 экзамен: НЕ НАЧАЛСЯ, время удерживается",
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 👤 сессий сегодня: {len([v for v in user_behaviour['visits'] if datetime.datetime.fromisoformat(v).date() == datetime.date.today()])}",
    ]
    return logs

@app.get("/api/random_avatar")
async def random_avatar():
    fake_names = [
        "Толик_228", "Саня_без_дома", "Серый_22", "Колян_85", 
        "Батя_с_палкой", "Рыжий_кот", "Сосед_Гена", "Мамкин_алкаш",
        "Дворник_Петрович", "Бомж_Аркадий", "Шурик_с_пивом"
    ]
    return {"avatar": f"https://api.dicebear.com/7.x/pixel-art/svg?seed={random.choice(fake_names)}", "name": random.choice(fake_names)}

# Создаём шаблоны
def create_templates():
    os.makedirs("templates", exist_ok=True)
    
    with open("templates/exam_check.html", "w", encoding="utf-8") as f:
        f.write("""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ТЕРМИНАЛ ДОСТУПА</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            min-height: 100vh;
            background: radial-gradient(ellipse at center, #0a0a0a 0%, #000000 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Courier New', 'Fira Code', monospace;
            position: relative;
            overflow: hidden;
        }
        
        /* CRT эффект */
        body::before {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: repeating-linear-gradient(
                0deg,
                rgba(0, 255, 0, 0.03) 0px,
                rgba(0, 255, 0, 0.03) 2px,
                transparent 2px,
                transparent 4px
            );
            pointer-events: none;
            z-index: 1;
        }
        
        body::after {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: radial-gradient(circle, transparent 50%, rgba(0,0,0,0.5) 100%);
            pointer-events: none;
            z-index: 1;
        }
        
        .container {
            position: relative;
            z-index: 2;
            background: rgba(0, 0, 0, 0.85);
            backdrop-filter: blur(8px);
            border: 2px solid #00ff00;
            box-shadow: 0 0 30px rgba(0, 255, 0, 0.3), inset 0 0 20px rgba(0, 255, 0, 0.1);
            padding: 3rem 4rem;
            text-align: center;
            animation: glitch 0.3s infinite;
        }
        
        @keyframes glitch {
            0%, 100% { transform: skew(0deg, 0deg); opacity: 1; }
            95% { transform: skew(0.5deg, 0.2deg); opacity: 0.95; }
            96% { transform: skew(-0.3deg, -0.1deg); }
        }
        
        h1 {
            color: #00ff00;
            font-size: 2rem;
            letter-spacing: 4px;
            text-shadow: 0 0 10px #00ff00, 0 0 20px #00ff00;
            margin-bottom: 2rem;
            font-weight: normal;
            border-right: 2px solid #00ff00;
            display: inline-block;
            padding-right: 1rem;
            animation: blink 1s step-end infinite;
        }
        
        @keyframes blink {
            0%, 100% { border-color: #00ff00; }
            50% { border-color: transparent; }
        }
        
        .buttons {
            display: flex;
            gap: 30px;
            justify-content: center;
            margin: 2rem 0;
        }
        
        button {
            background: transparent;
            border: 2px solid #00ff00;
            color: #00ff00;
            padding: 12px 28px;
            font-family: monospace;
            font-size: 1.2rem;
            cursor: pointer;
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        
        button::before {
            content: "";
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 0, 0.3), transparent);
            transition: left 0.5s;
        }
        
        button:hover::before {
            left: 100%;
        }
        
        button:hover {
            background: rgba(0, 255, 0, 0.1);
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.5);
            transform: scale(1.05);
        }
        
        .footnote {
            color: #00aa00;
            font-size: 0.7rem;
            opacity: 0.6;
            margin-top: 2rem;
            letter-spacing: 1px;
        }
        
        .scanline {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(
                to bottom,
                transparent 50%,
                rgba(0, 255, 0, 0.03) 50%
            );
            background-size: 100% 4px;
            pointer-events: none;
            animation: scan 8s linear infinite;
            z-index: 3;
        }
        
        @keyframes scan {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100%); }
        }
        
        @media (max-width: 600px) {
            .container { padding: 2rem; margin: 1rem; }
            h1 { font-size: 1.3rem; }
            button { padding: 8px 20px; font-size: 1rem; }
            .buttons { gap: 15px; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="container">
        <h1>> ЭКЗАМЕН СДАН?</h1>
        <div class="buttons">
            <button onclick="select('ещё нет')">[ ещё нет ]</button>
            <button onclick="select('забыл')">[ забыл ]</button>
        </div>
        <div class="footnote">* выбор необратим. время будет остановлено.</div>
    </div>
    <script>
        async function select(choice) {
            const res = await fetch('/enter', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({choice: choice})
            });
            if (res.ok) window.location.href = '/hub';
        }
    </script>
</body>
</html>
        """)
    
    with open("templates/hub.html", "w", encoding="utf-8") as f:
        f.write("""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>ТЕХНИЧЕСКИЙ ХАБ :: ВРЕМЯ ОСТАНОВЛЕНО</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        :root {
            --bg-color: {{ '#0a1a1a' if rain_mode else '#0a0a12' }};
            --panel-bg: rgba(5, 10, 15, 0.85);
            --accent: {{ '#2a9e8c' if rain_mode else '#2a7f6e' }};
            --glow: {{ '#2a9e8c' if rain_mode else '#2a7f6e' }};
            --text: #b0ffc0;
            --border: {{ '#2a9e8c' if rain_mode else '#2a7f6e' }};
        }
        
        body {
            background: var(--bg-color);
            color: var(--text);
            font-family: 'Courier New', 'Fira Code', monospace;
            padding: 20px;
            transition: background 0.8s ease;
            position: relative;
            overflow-x: hidden;
        }
        
        /* CRT эффект */
        body::before {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: repeating-linear-gradient(
                0deg,
                rgba(0, 255, 100, 0.02) 0px,
                rgba(0, 255, 100, 0.02) 2px,
                transparent 2px,
                transparent 4px
            );
            pointer-events: none;
            z-index: 999;
        }
        
        /* VHS эффект */
        .vhs {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, 
                transparent 0%, 
                rgba(255, 255, 255, 0.02) 50%, 
                transparent 100%);
            animation: vhsMove 0.2s linear infinite;
            pointer-events: none;
            z-index: 998;
        }
        
        @keyframes vhsMove {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        .dashboard {
            max-width: 1600px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            position: relative;
            z-index: 1;
        }
        
        .panel {
            background: var(--panel-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 18px;
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
        }
        
        .panel::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent), transparent);
            animation: scanHorizontal 3s linear infinite;
        }
        
        @keyframes scanHorizontal {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        .panel h2 {
            font-size: 0.85rem;
            letter-spacing: 2px;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border);
            display: inline-block;
            text-transform: uppercase;
            font-weight: normal;
        }
        
        /* Камера */
        .camera-view {
            background: #000000aa;
            border-radius: 2px;
            height: 320px;
            overflow-y: auto;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            padding: 15px;
            border: 1px solid #2a5a5a;
            position: relative;
        }
        
        .camera-view::-webkit-scrollbar {
            width: 4px;
            background: #1a3a3a;
        }
        
        .camera-view::-webkit-scrollbar-thumb {
            background: var(--accent);
        }
        
        .avatar-card {
            background: #0a1a1a;
            border-radius: 2px;
            padding: 8px;
            text-align: center;
            width: 85px;
            border: 1px solid #2a6a6a;
            transition: all 0.2s;
            cursor: pointer;
        }
        
        .avatar-card:hover {
            transform: scale(1.05);
            border-color: var(--accent);
            box-shadow: 0 0 10px rgba(42, 158, 140, 0.5);
        }
        
        .avatar-card img {
            width: 60px;
            height: 60px;
            image-rendering: pixelated;
        }
        
        .avatar-card div {
            font-size: 0.7rem;
            margin-top: 5px;
            color: #8ac8b0;
        }
        
        /* Радар */
        .radar-container {
            position: relative;
            display: flex;
            justify-content: center;
            margin: 15px 0;
        }
        
        .radar {
            position: relative;
            width: 280px;
            height: 280px;
            border-radius: 50%;
            background: radial-gradient(circle, #001010, #000a0a);
            border: 2px solid var(--accent);
            box-shadow: 0 0 20px rgba(42, 158, 140, 0.3);
            overflow: hidden;
        }
        
        .radar-sweep {
            position: absolute;
            top: 0;
            left: 0;
            width: 50%;
            height: 50%;
            background: linear-gradient(135deg, rgba(42, 158, 140, 0.4) 0%, transparent 100%);
            transform-origin: 0% 100%;
            animation: sweep 4s linear infinite;
            border-radius: 0 0 0 100%;
        }
        
        @keyframes sweep {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        .vacuum-dot {
            position: absolute;
            width: 12px;
            height: 12px;
            background: #ffaa44;
            border-radius: 50%;
            box-shadow: 0 0 12px #ffaa44;
            transition: all 0.2s ease-out;
            z-index: 10;
        }
        
        .vacuum-dot::after {
            content: "●";
            position: absolute;
            top: -8px;
            left: -8px;
            color: #ffaa44;
            font-size: 24px;
            opacity: 0.6;
        }
        
        .radar-grid {
            position: absolute;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            background: radial-gradient(circle, transparent 0%, transparent 48%, var(--accent) 48%, var(--accent) 50%, transparent 50%),
                        radial-gradient(circle, transparent 0%, transparent 73%, var(--accent) 73%, var(--accent) 75%, transparent 75%);
            opacity: 0.3;
        }
        
        /* Таймер */
        .timer {
            font-size: 4rem;
            text-align: center;
            font-family: monospace;
            letter-spacing: 8px;
            font-weight: bold;
            text-shadow: 0 0 20px var(--accent);
            background: #00000066;
            padding: 20px;
            border-radius: 4px;
        }
        
        /* Матрица */
        .matrix {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin: 20px 0;
        }
        
        .matrix-btn {
            background: #0a151a;
            border: 1px solid #2a5a6a;
            padding: 12px 8px;
            text-align: center;
            cursor: pointer;
            font-size: 0.75rem;
            transition: all 0.1s;
            font-family: monospace;
            color: #6a9a8a;
        }
        
        .matrix-btn:hover {
            background: #1a3a3a;
            border-color: var(--accent);
        }
        
        .matrix-btn.selected {
            background: #2a6a7a;
            border-color: #8accee;
            color: white;
            box-shadow: 0 0 12px var(--accent);
        }
        
        button {
            background: transparent;
            border: 2px solid var(--accent);
            color: var(--accent);
            padding: 10px 20px;
            font-family: monospace;
            cursor: pointer;
            transition: all 0.3s;
            text-transform: uppercase;
            font-weight: bold;
            letter-spacing: 2px;
        }
        
        button:hover {
            background: rgba(42, 158, 140, 0.2);
            box-shadow: 0 0 15px var(--accent);
        }
        
        .logs {
            background: #000000aa;
            font-family: monospace;
            font-size: 0.7rem;
            height: 140px;
            overflow-y: auto;
            padding: 12px;
            border: 1px solid #2a5a5a;
        }
        
        .logs div {
            padding: 2px 0;
            border-left: 2px solid var(--accent);
            padding-left: 8px;
            margin: 4px 0;
        }
        
        .status-text {
            font-size: 0.7rem;
            text-align: center;
            margin-top: 12px;
            color: #6a9e8a;
        }
        
        @media (max-width: 900px) {
            .dashboard { grid-template-columns: 1fr; }
            .timer { font-size: 2.5rem; letter-spacing: 4px; }
            .radar { width: 220px; height: 220px; }
        }
        
        .glitch-text {
            animation: textGlitch 0.3s infinite;
        }
        
        @keyframes textGlitch {
            0%, 100% { text-shadow: 2px 0 0 rgba(255,0,0,0.5), -2px 0 0 rgba(0,255,0,0.5); }
            50% { text-shadow: -2px 0 0 rgba(255,0,0,0.5), 2px 0 0 rgba(0,255,0,0.5); }
        }
    </style>
</head>
<body>
    <div class="vhs"></div>
    <div class="dashboard">
        <div class="panel">
            <h2>📹 CCTV-05 | ПЯТЁРОЧКА.ДВОР</h2>
            <div id="cameraFeed" class="camera-view">
                <div style="color: #4a7a6a; text-align: center; width: 100%;">ЗАГРУЗКА ПОТОКА...</div>
            </div>
            <div class="status-text">⚡ лица заменены на аватары из telegram-чатов</div>
        </div>
        
        <div class="panel">
            <h2>🌀 ROBOROCK S6 | ТЕЛЕМЕТРИЯ</h2>
            <div class="radar-container">
                <div class="radar">
                    <div class="radar-sweep"></div>
                    <div class="radar-grid"></div>
                    <div id="vacuumDot" class="vacuum-dot" style="left: 50%; top: 50%;"></div>
                </div>
            </div>
            <div class="status-text">🔊 АУДИОПЕТЛЯ: ШУМ РАБОТЫ | МАРШРУТ ПО СХЕМЕ КВАРТИРЫ</div>
            <audio id="vacuumAudio" loop>
                <source src="https://www.soundjay.com/misc/sounds/vacuum-cleaner-01.mp3" type="audio/mpeg">
            </audio>
        </div>
        
        <div class="panel">
            <h2>⏱️ SESSION::TIMER | ЭКЗАМЕН</h2>
            <div id="timerDisplay" class="timer">00:00</div>
            <div id="timerMsg" class="status-text">[ ОЖИДАНИЕ СТАРТА ]</div>
        </div>
        
        <div class="panel">
            <h2>🧠 AI-MATRIX | КОММУТАТОР 4x4</h2>
            <div class="matrix" id="matrix"></div>
            <button id="commutateBtn">▶ КОММУТИРОВАТЬ</button>
            <div id="commutateResult" class="status-text"></div>
        </div>
    </div>
    
    <div style="margin-top: 20px; max-width: 1600px; margin-left: auto; margin-right: auto;">
        <div class="panel">
            <h2>📟 SYSTEM::LOGS (STDOUT)</h2>
            <div id="logContainer" class="logs">
                <div>[---] инициализация хаба...</div>
            </div>
        </div>
    </div>
    
    <script>
        let timerSeconds = 0;
        let timerInterval = null;
        let selectedMatrix = Array(16).fill(false);
        
        async function initTimer() {
            const res = await fetch('/api/timer');
            const data = await res.json();
            timerSeconds = data.seconds;
            updateTimerDisplay();
            if (timerInterval) clearInterval(timerInterval);
            timerInterval = setInterval(() => {
                if (timerSeconds > 0) {
                    timerSeconds--;
                    updateTimerDisplay();
                    if (timerSeconds === 0) {
                        clearInterval(timerInterval);
                        document.getElementById('timerMsg').innerHTML = '⏸️ ВРЕМЯ ОСТАНОВИЛОСЬ. МОЖЕШЬ КУРИТЬ.';
                        const audio = document.getElementById('vacuumAudio');
                        if (audio) audio.volume = 0;
                    }
                }
            }, 1000);
        }
        
        function updateTimerDisplay() {
            const mins = Math.floor(timerSeconds / 60);
            const secs = timerSeconds % 60;
            document.getElementById('timerDisplay').innerText = `${mins.toString().padStart(2,'0')}:${secs.toString().padStart(2,'0')}`;
        }
        
        function initVacuumStream() {
            const evtSource = new EventSource('/api/vacuum_stream');
            evtSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                const leftPercent = (data.x / 10) * 100;
                const topPercent = (data.y / 10) * 100;
                const dot = document.getElementById('vacuumDot');
                dot.style.left = `calc(${leftPercent}% - 6px)`;
                dot.style.top = `calc(${topPercent}% - 6px)`;
            };
            
            const audio = document.getElementById('vacuumAudio');
            audio.volume = 0.25;
            audio.play().catch(e => console.log('audio autoplay blocked'));
        }
        
        async function updateCamera() {
            const container = document.getElementById('cameraFeed');
            const count = Math.floor(Math.random() * 8) + 6;
            let html = '';
            for(let i = 0; i < count; i++) {
                const res = await fetch('/api/random_avatar');
                const avatar = await res.json();
                html += `
                    <div class="avatar-card" onclick="alert('${avatar.name} | уровень опьянения: ${Math.floor(Math.random() * 100)}%')">
                        <img src="${avatar.avatar}" alt="avatar">
                        <div>${avatar.name}</div>
                    </div>
                `;
            }
            container.innerHTML = html;
        }
        
        function buildMatrix() {
            const container = document.getElementById('matrix');
            container.innerHTML = '';
            const labels = ['ФОТО', 'TEXT', 'ДОЖДЬ', 'CCTV'];
            for(let i = 0; i < 16; i++) {
                const btn = document.createElement('div');
                const row = Math.floor(i / 4);
                const col = i % 4;
                btn.className = 'matrix-btn';
                btn.innerText = `${labels[row]}:${col+1}`;
                btn.onclick = () => {
                    selectedMatrix[i] = !selectedMatrix[i];
                    if(selectedMatrix[i]) btn.classList.add('selected');
                    else btn.classList.remove('selected');
                };
                container.appendChild(btn);
            }
        }
        
        async function sendCommutation() {
            const inputs = [];
            for(let i = 0; i < 16; i++) {
                if(selectedMatrix[i]) inputs.push(i);
            }
            const res = await fetch('/api/commutate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ inputs: inputs })
            });
            const data = await res.json();
            document.getElementById('commutateResult').innerHTML = data.message.replace(/\\n/g, '<br>');
            selectedMatrix.fill(false);
            document.querySelectorAll('.matrix-btn').forEach(btn => btn.classList.remove('selected'));
            
            setTimeout(() => {
                document.getElementById('commutateResult').innerHTML = '';
            }, 3000);
        }
        
        async function fetchLogs() {
            const res = await fetch('/api/logs');
            const logs = await res.json();
            const container = document.getElementById('logContainer');
            container.innerHTML = logs.map(l => `<div>${l}</div>`).join('');
        }
        
        window.onload = () => {
            initTimer();
            initVacuumStream();
            buildMatrix();
            updateCamera();
            fetchLogs();
            setInterval(updateCamera, 18000);
            setInterval(fetchLogs, 10000);
            document.getElementById('commutateBtn').onclick = sendCommutation;
        };
        
        window.onbeforeunload = () => {
            if(timerSeconds > 0) {
                return "Таймер будет сброшен. Время продолжится?";
            }
        };
    </script>
</body>
</html>
        """)

create_templates()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
