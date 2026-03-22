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

# --- Инициализация приложения ---
app = FastAPI(title="Временной Хаб", description="Ловушка для остановленного времени")

# Создаем директории для статики и шаблонов, если их нет
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("user_data", exist_ok=True)  # для хранения схемы квартиры и "обучения"

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Глобальные состояния (имитация сессии и ИИ) ---
# В реальном проекте это хранилось бы в Redis/БД, но для атмосферы оставим в памяти
user_behaviour = {
    "visits": [],
    "last_commutation": None,
    "rain_mode": False
}

# Схема квартиры (по умолчанию, потом пользователь загружает свою)
apartment_map = {
    "walls": [(0, 0), (10, 0), (10, 10), (0, 10)],
    "obstacles": [(2, 2), (7, 7)],
    "vacuum_pos": [5.0, 5.0]
}

# --- Вспомогательные функции ---
async def get_weather_rain_status():
    """Проверяет, идет ли дождь по API (имитация или реальный запрос)"""
    # Для реализма используем бесплатный API wttr.in или имитацию
    try:
        async with aiohttp.ClientSession() as session:
            # Запрос к wttr.in в формате JSON для Amsterdam (можно заменить на город пользователя)
            async with session.get("https://wttr.in/Amsterdam?format=j1") as resp:
                data = await resp.json()
                current_condition = data.get("current_condition", [{}])[0]
                weather_desc = current_condition.get("weatherDesc", [{}])[0].get("value", "").lower()
                is_raining = "rain" in weather_desc or "drizzle" in weather_desc
                return is_raining
    except:
        # Если API недоступно, используем случайное состояние с 30% вероятностью дождя
        # Или можно просто вернуть False, но для вайба лучше рандом
        return random.random() < 0.3

# --- Эндпоинты ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница: экзамен?"""
    return templates.TemplateResponse("exam_check.html", {"request": request})

@app.post("/enter")
async def enter_site(data: dict):
    """Обработка выбора 'ещё нет' или 'забыл'"""
    choice = data.get("choice")
    if choice not in ["ещё нет", "забыл"]:
        raise HTTPException(status_code=400, detail="Неверный выбор")
    # Записываем время входа для "ИИ-обучения"
    user_behaviour["visits"].append(datetime.datetime.now().isoformat())
    return {"status": "ok", "redirect": "/hub"}

@app.get("/hub", response_class=HTMLResponse)
async def hub(request: Request):
    """Главный интерфейс - ловушка времени"""
    # Проверяем погоду для цветовой схемы
    is_raining = await get_weather_rain_status()
    user_behaviour["rain_mode"] = is_raining
    
    return templates.TemplateResponse("hub.html", {
        "request": request,
        "rain_mode": is_raining
    })

@app.get("/api/timer")
async def get_timer():
    """Возвращает случайное время для таймера (2-47 минут) в секундах"""
    minutes = random.randint(2, 47)
    return {"seconds": minutes * 60, "minutes": minutes}

@app.get("/api/vacuum_stream")
async def vacuum_stream():
    """Генерирует поток данных о положении пылесоса для радара"""
    async def generate():
        while True:
            # Хаотичное движение по схеме квартиры
            x, y = apartment_map["vacuum_pos"]
            # Добавляем случайное смещение + отскок от стен (упрощенно)
            dx = random.uniform(-0.5, 0.5)
            dy = random.uniform(-0.5, 0.5)
            new_x = max(0.5, min(9.5, x + dx))
            new_y = max(0.5, min(9.5, y + dy))
            apartment_map["vacuum_pos"] = [new_x, new_y]
            
            data = {
                "x": new_x,
                "y": new_y,
                "walls": apartment_map["walls"],
                "obstacles": apartment_map["obstacles"]
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(random.uniform(0.8, 2.2))  # случайная задержка как в реальном пылесосе
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/upload_apartment")
async def upload_apartment(data: dict):
    """Пользователь загружает схему своей квартиры (один раз при настройке)"""
    global apartment_map
    # Ожидаем walls: list of points, obstacles: list of points
    if "walls" in data and "obstacles" in data:
        apartment_map["walls"] = data["walls"]
        apartment_map["obstacles"] = data["obstacles"]
        # Сохраняем в файл
        with open("user_data/apartment_map.json", "w") as f:
            json.dump(apartment_map, f)
        return {"status": "ok", "message": "Схема квартиры загружена"}
    else:
        raise HTTPException(status_code=400, detail="Неверный формат схемы")

@app.post("/api/commutate")
async def commutate(request: Request):
    """ИИ-коммутатор 4x4. Принимает данные о том, какой канал выбран"""
    data = await request.json()
    # Логируем для "обучения"
    user_behaviour["last_commutation"] = {
        "time": datetime.datetime.now().isoformat(),
        "inputs": data.get("inputs", [])
    }
    # Сохраняем историю для "обучения"
    with open("user_data/commutations.json", "a") as f:
        f.write(json.dumps(user_behaviour["last_commutation"]) + "\n")
    
    # "Результат отправлен мне" - просто возвращаем сообщение
    return {"message": "Результат отправлен мне. Спасибо за участие в сессии."}

@app.get("/api/logs")
async def get_logs():
    """Технический блог в виде логов stdout"""
    logs = [
        f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] дождь: {'да, вайб' if user_behaviour['rain_mode'] else 'нет, сухо'}",
        f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] пылесос: врезался в стену, продолжает",
        f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] экзамен: не начался, время удерживается",
        f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] посетитель: активен, коммутаций: {len(user_behaviour.get('commutations_history', []))}",
    ]
    return logs

@app.get("/api/random_avatar")
async def random_avatar():
    """Генерирует случайный аватар на основе ников из Telegram (имитация)"""
    # В реальности тут был бы парсинг чатов, но для атмосферы - случайные имена
    fake_names = ["Кот_Питон", "Мрачный_Технарь", "Алкаш_из_5ки", "Сосед_Сверху", "Нейросеть", "Хаос", "Дождь"]
    return {"avatar": f"https://api.dicebear.com/7.x/identicon/svg?seed={random.choice(fake_names)}", "name": random.choice(fake_names)}

# --- Шаблоны (встроенные строки для удобства, но можно вынести в файлы) ---
# Создадим файлы шаблонов, если их нет
def create_templates():
    os.makedirs("templates", exist_ok=True)
    
    # Шаблон exam_check.html
    with open("templates/exam_check.html", "w", encoding="utf-8") as f:
        f.write("""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход в хаб | Остановка времени</title>
    <style>
        body {
            background: #0a0f1a;
            color: #a0b0c0;
            font-family: 'Courier New', monospace;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .container {
            background: #141a24;
            padding: 2rem;
            border-radius: 8px;
            border: 1px solid #2a3a4a;
            text-align: center;
            box-shadow: 0 0 20px rgba(0,0,0,0.5);
        }
        h1 {
            font-size: 1.5rem;
            margin-bottom: 2rem;
            font-weight: normal;
            letter-spacing: 2px;
        }
        .buttons {
            display: flex;
            gap: 20px;
            justify-content: center;
        }
        button {
            background: #1e2a32;
            border: 1px solid #3a5a6a;
            color: #c0d0e0;
            padding: 10px 20px;
            font-family: inherit;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        button:hover {
            background: #2a3a44;
            border-color: #6a8a9a;
            color: white;
        }
        .footnote {
            margin-top: 2rem;
            font-size: 0.7rem;
            opacity: 0.6;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Экзамен сдан?</h1>
        <div class="buttons">
            <button onclick="select('ещё нет')">ещё нет</button>
            <button onclick="select('забыл')">забыл</button>
        </div>
        <div class="footnote">выбор необратим</div>
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
    
    # Шаблон hub.html (основной интерфейс)
    with open("templates/hub.html", "w", encoding="utf-8") as f:
        f.write("""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Технический хаб | Время остановлено</title>
    <style>
        * {
            box-sizing: border-box;
        }
        body {
            margin: 0;
            background: {{ '#1a2a2f' if rain_mode else '#1a1e2a' }};
            font-family: 'Segoe UI', 'Courier New', monospace;
            color: #cde3f0;
            transition: background 0.5s ease;
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: rgba(10, 15, 20, 0.8);
            backdrop-filter: blur(5px);
            border: 1px solid #2c4c5c;
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .panel h2 {
            margin-top: 0;
            font-size: 1.2rem;
            border-bottom: 1px solid #2c5c6c;
            display: inline-block;
        }
        .camera-view {
            background: #00000066;
            border-radius: 8px;
            height: 300px;
            overflow-y: auto;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            padding: 10px;
        }
        .avatar-card {
            background: #1e2a2e;
            border-radius: 8px;
            padding: 8px;
            text-align: center;
            width: 80px;
        }
        .avatar-card img {
            width: 64px;
            height: 64px;
            border-radius: 50%;
        }
        .radar {
            background: #0f1219;
            border-radius: 50%;
            width: 250px;
            height: 250px;
            margin: 20px auto;
            position: relative;
            border: 1px solid #2c9c8c;
            box-shadow: 0 0 10px rgba(0,255,200,0.2);
        }
        .vacuum-dot {
            width: 12px;
            height: 12px;
            background: #ffaa44;
            border-radius: 50%;
            position: absolute;
            transition: all 0.2s linear;
            box-shadow: 0 0 8px orange;
        }
        .timer {
            font-size: 3rem;
            text-align: center;
            font-family: monospace;
            letter-spacing: 5px;
        }
        .matrix {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin: 20px 0;
        }
        .matrix-btn {
            background: #1a2a32;
            border: 1px solid #3a6a7a;
            padding: 12px;
            text-align: center;
            cursor: pointer;
            font-size: 0.8rem;
            transition: 0.1s linear;
        }
        .matrix-btn.selected {
            background: #2a6a7a;
            border-color: #8accee;
            box-shadow: 0 0 6px cyan;
        }
        .logs {
            background: #0b0e14;
            font-family: monospace;
            font-size: 0.75rem;
            height: 150px;
            overflow-y: auto;
            padding: 8px;
        }
        .status-text {
            font-size: 0.8rem;
            text-align: center;
            margin-top: 15px;
        }
        @media (max-width: 800px) {
            .dashboard { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
<div class="dashboard">
    <!-- Пятёрочка (видеонаблюдение) -->
    <div class="panel">
        <h2>📹 Пятёрочка (видеонаблюдение)</h2>
        <div id="cameraFeed" class="camera-view">
            <!-- Аватары будут подгружаться -->
        </div>
        <div class="status-text">* лица алкашей заменены на аватары из Telegram-чатов</div>
    </div>
    
    <!-- Пылесос (аудио) + радар -->
    <div class="panel">
        <h2>🌀 Пылесос (аудио)</h2>
        <div id="radarContainer" class="radar">
            <div id="vacuumDot" class="vacuum-dot" style="left: 50%; top: 50%;"></div>
        </div>
        <div class="status-text">шум петли: активен | маршрут по схеме квартиры</div>
        <audio id="vacuumAudio" loop autoplay>
            <source src="https://www.soundjay.com/misc/sounds/vacuum-cleaner-01.mp3" type="audio/mpeg">
        </audio>
        <script>document.getElementById('vacuumAudio').volume = 0.3;</script>
    </div>
    
    <!-- Сессия (таймер) -->
    <div class="panel">
        <h2>⏱️ Сессия (обратный отсчёт)</h2>
        <div id="timerDisplay" class="timer">--:--</div>
        <div id="timerMsg" class="status-text">ожидание...</div>
    </div>
    
    <!-- ИИ-коммутатор 4x4 -->
    <div class="panel">
        <h2>🧠 ИИ-коммутатор</h2>
        <div class="matrix" id="matrix">
            <!-- JS заполнит 16 кнопок -->
        </div>
        <button id="commutateBtn" style="width:100%; margin-top:10px;">Коммутировать → отправить сессию</button>
        <div id="commutateResult" class="status-text"></div>
    </div>
</div>

<!-- Блок логов -->
<div style="padding: 0 20px 20px 20px;">
    <div class="panel">
        <h2>📟 stdout / технический блог</h2>
        <div id="logContainer" class="logs"></div>
    </div>
</div>

<script>
    // --- Состояния ---
    let timerSeconds = 0;
    let timerInterval = null;
    let selectedMatrix = Array(16).fill(false);
    
    // --- Загрузка таймера с сервера ---
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
                    document.getElementById('timerMsg').innerHTML = 'Время остановилось. Можешь курить.';
                    // Тишина вместо звука
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
    
    // --- Поток пылесоса (SSE) ---
    function initVacuumStream() {
        const evtSource = new EventSource('/api/vacuum_stream');
        evtSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            // Переводим координаты (0-10) в проценты для радара
            const leftPercent = (data.x / 10) * 100;
            const topPercent = (data.y / 10) * 100;
            const dot = document.getElementById('vacuumDot');
            dot.style.left = `calc(${leftPercent}% - 6px)`;
            dot.style.top = `calc(${topPercent}% - 6px)`;
        };
    }
    
    // --- Поток камеры: периодически обновляем аватары ---
    async function updateCamera() {
        const container = document.getElementById('cameraFeed');
        // Генерируем 6-8 аватаров (как будто люди во дворе)
        const count = Math.floor(Math.random() * 5) + 5;
        let html = '';
        for(let i=0; i<count; i++) {
            const res = await fetch('/api/random_avatar');
            const avatar = await res.json();
            html += `
                <div class="avatar-card">
                    <img src="${avatar.avatar}" alt="avatar">
                    <div>${avatar.name}</div>
                </div>
            `;
        }
        container.innerHTML = html;
    }
    
    // --- ИИ-коммутатор: создать матрицу ---
    function buildMatrix() {
        const container = document.getElementById('matrix');
        container.innerHTML = '';
        for(let i=0; i<16; i++) {
            const btn = document.createElement('div');
            btn.className = 'matrix-btn';
            btn.innerText = `вх${Math.floor(i/4)+1}/${(i%4)+1}`;
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
        for(let i=0; i<16; i++) {
            if(selectedMatrix[i]) inputs.push(i);
        }
        const res = await fetch('/api/commutate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ inputs: inputs })
        });
        const data = await res.json();
        document.getElementById('commutateResult').innerText = data.message;
        // сбросить выделение
        selectedMatrix.fill(false);
        document.querySelectorAll('.matrix-btn').forEach(btn => btn.classList.remove('selected'));
    }
    
    // --- Логи ---
    async function fetchLogs() {
        const res = await fetch('/api/logs');
        const logs = await res.json();
        const container = document.getElementById('logContainer');
        container.innerHTML = logs.map(l => `<div>${l}</div>`).join('');
    }
    
    // --- Обновление погоды (цветовая гамма через CSS уже применена из шаблона, но динамически проверим)---
    async function refreshWeatherUI() {
        // можно ничего не делать, бекенд уже передал rain_mode
    }
    
    // --- Сброс таймера при обновлении страницы (поведение) ---
    window.onload = () => {
        initTimer();
        initVacuumStream();
        buildMatrix();
        updateCamera();
        fetchLogs();
        setInterval(updateCamera, 15000); // новые лица каждые 15 сек
        setInterval(fetchLogs, 10000);
        document.getElementById('commutateBtn').onclick = sendCommutation;
        
        // Принудительно обновляем таймер при каждом фокусе? нет, оставим как есть
        // Если пользователь обновит страницу, таймер сбросится (новый запрос /api/timer)
    };
    
    // Дополнительно: если таймер закончился, ничего не делаем, просто тишина.
</script>
</body>
</html>
        """)
    
    # Создаем пустые файлы для хранения данных
    if not os.path.exists("user_data/apartment_map.json"):
        with open("user_data/apartment_map.json", "w") as f:
            json.dump(apartment_map, f)

create_templates()

# --- Запуск ---
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")