Starting SoulLink Tracker on Windows...
Installing Python dependencies...
Defaulting to user installation because normal site-packages is not writeable
Requirement already satisfied: fastapi>=0.104.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 5)) (0.116.1)
Requirement already satisfied: uvicorn>=0.24.0 in c:\program files\python312\lib\site-packages (from uvicorn[standard]>=0.24.0->-r requirements.txt (line 6)) (0.35.0)
Requirement already satisfied: python-multipart>=0.0.6 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 7)) (0.0.20)
Requirement already satisfied: sqlalchemy>=2.0.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 10)) (2.0.42)
Requirement already satisfied: alembic>=1.12.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 11)) (1.16.4)
Requirement already satisfied: aiosqlite>=0.19.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 12)) (0.21.0)
Requirement already satisfied: pydantic>=2.5.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 15)) (2.11.7)
Requirement already satisfied: websockets>=12.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 16)) (15.0.1)
Requirement already satisfied: cryptography>=41.0.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 19)) (45.0.5)
Requirement already satisfied: python-jose>=3.3.0 in c:\program files\python312\lib\site-packages (from python-jose[cryptography]>=3.3.0->-r requirements.txt (line 20)) (3.5.0)
Requirement already satisfied: passlib>=1.7.4 in c:\program files\python312\lib\site-packages (from passlib[bcrypt]>=1.7.4->-r requirements.txt (line 21)) (1.7.4)
Requirement already satisfied: pillow>=10.0.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 25)) (11.3.0)
Requirement already satisfied: pystray>=0.19.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 26)) (0.19.5)
Requirement already satisfied: requests>=2.31.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 29)) (2.32.4)
Requirement already satisfied: pyinstaller>=6.0.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 32)) (6.15.0)
Requirement already satisfied: pytest>=7.4.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 35)) (8.4.1)
Requirement already satisfied: pytest-asyncio>=0.21.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 36)) (1.1.0)
Requirement already satisfied: pytest-cov>=4.1.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 37)) (6.2.1)
Requirement already satisfied: pytest-playwright>=0.4.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 38)) (0.7.0)
Requirement already satisfied: hypothesis>=6.88.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 39)) (6.138.1)
Requirement already satisfied: httpx>=0.25.0 in c:\program files\python312\lib\site-packages (from -r requirements.txt (line 40)) (0.28.1)
Requirement already satisfied: starlette<0.48.0,>=0.40.0 in c:\program files\python312\lib\site-packages (from fastapi>=0.104.0->-r requirements.txt (line 5)) (0.47.2)
Requirement already satisfied: typing-extensions>=4.8.0 in c:\program files\python312\lib\site-packages (from fastapi>=0.104.0->-r requirements.txt (line 5)) (4.14.1)
Requirement already satisfied: annotated-types>=0.6.0 in c:\program files\python312\lib\site-packages (from pydantic>=2.5.0->-r requirements.txt (line 15)) (0.7.0)
Requirement already satisfied: pydantic-core==2.33.2 in c:\program files\python312\lib\site-packages (from pydantic>=2.5.0->-r requirements.txt (line 15)) (2.33.2)
Requirement already satisfied: typing-inspection>=0.4.0 in c:\program files\python312\lib\site-packages (from pydantic>=2.5.0->-r requirements.txt (line 15)) (0.4.1)
Requirement already satisfied: anyio<5,>=3.6.2 in c:\program files\python312\lib\site-packages (from starlette<0.48.0,>=0.40.0->fastapi>=0.104.0->-r requirements.txt (line 5)) (4.9.0)
Requirement already satisfied: idna>=2.8 in c:\program files\python312\lib\site-packages (from anyio<5,>=3.6.2->starlette<0.48.0,>=0.40.0->fastapi>=0.104.0->-r requirements.txt (line 5)) (3.10)
Requirement already satisfied: sniffio>=1.1 in c:\program files\python312\lib\site-packages (from anyio<5,>=3.6.2->starlette<0.48.0,>=0.40.0->fastapi>=0.104.0->-r requirements.txt (line 5)) (1.3.1)
Requirement already satisfied: click>=7.0 in c:\program files\python312\lib\site-packages (from uvicorn>=0.24.0->uvicorn[standard]>=0.24.0->-r requirements.txt (line 6)) (8.2.2)
Requirement already satisfied: h11>=0.8 in c:\program files\python312\lib\site-packages (from uvicorn>=0.24.0->uvicorn[standard]>=0.24.0->-r requirements.txt (line 6)) (0.16.0)
Requirement already satisfied: greenlet>=1 in c:\program files\python312\lib\site-packages (from sqlalchemy>=2.0.0->-r requirements.txt (line 10)) (3.2.3)
Requirement already satisfied: Mako in c:\program files\python312\lib\site-packages (from alembic>=1.12.0->-r requirements.txt (line 11)) (1.3.10)
Requirement already satisfied: cffi>=1.14 in c:\program files\python312\lib\site-packages (from cryptography>=41.0.0->-r requirements.txt (line 19)) (1.17.1)
Requirement already satisfied: ecdsa!=0.15 in c:\program files\python312\lib\site-packages (from python-jose>=3.3.0->python-jose[cryptography]>=3.3.0->-r requirements.txt (line 20)) (0.19.1)
Requirement already satisfied: rsa!=4.1.1,!=4.4,<5.0,>=4.0 in c:\program files\python312\lib\site-packages (from python-jose>=3.3.0->python-jose[cryptography]>=3.3.0->-r requirements.txt (line 20)) (4.9.1)
Requirement already satisfied: pyasn1>=0.5.0 in c:\program files\python312\lib\site-packages (from python-jose>=3.3.0->python-jose[cryptography]>=3.3.0->-r requirements.txt (line 20)) (0.6.1)
Requirement already satisfied: six in c:\users\alex\appdata\roaming\python\python312\site-packages (from pystray>=0.19.0->-r requirements.txt (line 26)) (1.16.0)
Requirement already satisfied: charset_normalizer<4,>=2 in c:\program files\python312\lib\site-packages (from requests>=2.31.0->-r requirements.txt (line 29)) (3.4.2)
Requirement already satisfied: urllib3<3,>=1.21.1 in c:\program files\python312\lib\site-packages (from requests>=2.31.0->-r requirements.txt (line 29)) (2.5.0)
Requirement already satisfied: certifi>=2017.4.17 in c:\program files\python312\lib\site-packages (from requests>=2.31.0->-r requirements.txt (line 29)) (2025.7.14)
Requirement already satisfied: setuptools>=42.0.0 in c:\program files\python312\lib\site-packages (from pyinstaller>=6.0.0->-r requirements.txt (line 32)) (80.9.0)
Requirement already satisfied: altgraph in c:\program files\python312\lib\site-packages (from pyinstaller>=6.0.0->-r requirements.txt (line 32)) (0.17.4)
Requirement already satisfied: pefile!=2024.8.26,>=2022.5.30 in c:\program files\python312\lib\site-packages (from pyinstaller>=6.0.0->-r requirements.txt (line 32)) (2023.2.7)
Requirement already satisfied: pywin32-ctypes>=0.2.1 in c:\program files\python312\lib\site-packages (from pyinstaller>=6.0.0->-r requirements.txt (line 32)) (0.2.3)
Requirement already satisfied: pyinstaller-hooks-contrib>=2025.8 in c:\program files\python312\lib\site-packages (from pyinstaller>=6.0.0->-r requirements.txt (line 32)) (2025.8)
Requirement already satisfied: packaging>=22.0 in c:\users\alex\appdata\roaming\python\python312\site-packages (from pyinstaller>=6.0.0->-r requirements.txt (line 32)) (23.2)
Requirement already satisfied: colorama>=0.4 in c:\users\alex\appdata\roaming\python\python312\site-packages (from pytest>=7.4.0->-r requirements.txt (line 35)) (0.4.6)
Requirement already satisfied: iniconfig>=1 in c:\program files\python312\lib\site-packages (from pytest>=7.4.0->-r requirements.txt (line 35)) (2.1.0)
Requirement already satisfied: pluggy<2,>=1.5 in c:\program files\python312\lib\site-packages (from pytest>=7.4.0->-r requirements.txt (line 35)) (1.6.0)
Requirement already satisfied: pygments>=2.7.2 in c:\users\alex\appdata\roaming\python\python312\site-packages (from pytest>=7.4.0->-r requirements.txt (line 35)) (2.16.1)
Requirement already satisfied: coverage>=7.5 in c:\program files\python312\lib\site-packages (from coverage[toml]>=7.5->pytest-cov>=4.1.0->-r requirements.txt (line 37)) (7.10.1)
Requirement already satisfied: playwright>=1.18 in c:\program files\python312\lib\site-packages (from pytest-playwright>=0.4.0->-r requirements.txt (line 38)) (1.54.0)
Requirement already satisfied: pytest-base-url<3.0.0,>=1.0.0 in c:\program files\python312\lib\site-packages (from pytest-playwright>=0.4.0->-r requirements.txt (line 38)) (2.1.0)
Requirement already satisfied: python-slugify<9.0.0,>=6.0.0 in c:\program files\python312\lib\site-packages (from pytest-playwright>=0.4.0->-r requirements.txt (line 38)) (8.0.4)
Requirement already satisfied: text-unidecode>=1.3 in c:\program files\python312\lib\site-packages (from python-slugify<9.0.0,>=6.0.0->pytest-playwright>=0.4.0->-r requirements.txt (line 38)) (1.3)
Requirement already satisfied: attrs>=22.2.0 in c:\program files\python312\lib\site-packages (from hypothesis>=6.88.0->-r requirements.txt (line 39)) (25.3.0)
Requirement already satisfied: sortedcontainers<3.0.0,>=2.1.0 in c:\program files\python312\lib\site-packages (from hypothesis>=6.88.0->-r requirements.txt (line 39)) (2.4.0)
Requirement already satisfied: httpcore==1.* in c:\program files\python312\lib\site-packages (from httpx>=0.25.0->-r requirements.txt (line 40)) (1.0.9)
Requirement already satisfied: pycparser in c:\program files\python312\lib\site-packages (from cffi>=1.14->cryptography>=41.0.0->-r requirements.txt (line 19)) (2.22)
Requirement already satisfied: bcrypt>=3.1.0 in c:\program files\python312\lib\site-packages (from passlib[bcrypt]>=1.7.4->-r requirements.txt (line 21)) (4.3.0)
Requirement already satisfied: pyee<14,>=13 in c:\program files\python312\lib\site-packages (from playwright>=1.18->pytest-playwright>=0.4.0->-r requirements.txt (line 38)) (13.0.0)
Requirement already satisfied: httptools>=0.6.3 in c:\program files\python312\lib\site-packages (from uvicorn[standard]>=0.24.0->-r requirements.txt (line 6)) (0.6.4)
Requirement already satisfied: python-dotenv>=0.13 in c:\program files\python312\lib\site-packages (from uvicorn[standard]>=0.24.0->-r requirements.txt (line 6)) (1.1.1)
Requirement already satisfied: pyyaml>=5.1 in c:\program files\python312\lib\site-packages (from uvicorn[standard]>=0.24.0->-r requirements.txt (line 6)) (6.0.2)
Requirement already satisfied: watchfiles>=0.13 in c:\program files\python312\lib\site-packages (from uvicorn[standard]>=0.24.0->-r requirements.txt (line 6)) (1.1.0)
Requirement already satisfied: MarkupSafe>=0.9.2 in c:\program files\python312\lib\site-packages (from Mako->alembic>=1.12.0->-r requirements.txt (line 11)) (3.0.2)

Starting SoulLink Tracker server...
🎮 SoulLink Tracker - Server Startup
✅ Added C:\Users\Alex\Downloads\soullink_tracker-fix-family-blocking-bug\soullink_tracker-fix-family-blocking-bug\src to Python path
✅ Set PYTHONPATH environment variable
📁 Project root: C:\Users\Alex\Downloads\soullink_tracker-fix-family-blocking-bug\soullink_tracker-fix-family-blocking-bug
📁 Source path: C:\Users\Alex\Downloads\soullink_tracker-fix-family-blocking-bug\soullink_tracker-fix-family-blocking-bug\src
🐍 Python executable: C:\Program Files\Python312\python.exe
🔗 Python path includes: ['C:\Users\Alex\Downloads\soullink_tracker-fix-family-blocking-bug\soullink_tracker-fix-family-blocking-bug\src', 'C:\Users\Alex\Downloads\soullink_tracker-fix-family-blocking-bug\soullink_tracker-fix-family-blocking-bug']
✅ soullink_tracker module can be imported successfully
✅ All required dependencies are installed
🔧 Running database migrations...
✅ Database migrations completed successfully
📊 Loading reference data...
✅ Reference data already loaded
🚀 Starting SoulLink Tracker server...
📍 Server will be available at: http://127.0.0.1:8000
🔧 Admin panel: http://127.0.0.1:8000/admin
📊 Dashboard: http://127.0.0.1:8000/dashboard
📖 API docs: http://127.0.0.1:8000/docs

📋 To create runs and players, use the admin panel in your browser
🔑 Players need: run name + player name + run password for their watchers

Press Ctrl+C to stop the server
INFO: Will watch for changes in these directories: ['C:\Users\Alex\Downloads\soullink_tracker-fix-family-blocking-bug\soullink_tracker-fix-family-blocking-bug']
INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO: Started reloader process [10128] using WatchFiles
INFO: Started server process [20636]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: 127.0.0.1:51772 - "GET /admin HTTP/1.1" 200 OK
INFO: 127.0.0.1:51772 - "GET /css/styles.css HTTP/1.1" 200 OK
INFO: 127.0.0.1:51772 - "GET /js/utils.js?v=1755894705980 HTTP/1.1" 200 OK
INFO: 127.0.0.1:51772 - "GET /js/admin-panel.js?v=1755894705980 HTTP/1.1" 200 OK
INFO: 127.0.0.1:51772 - "GET /v1/admin/runs HTTP/1.1" 200 OK
INFO: 127.0.0.1:51772 - "GET /health HTTP/1.1" 200 OK
INFO: 127.0.0.1:51771 - "GET /ready HTTP/1.1" 200 OK
INFO: 127.0.0.1:51778 - "POST /v1/admin/runs HTTP/1.1" 201 Created
INFO: 127.0.0.1:51778 - "GET /v1/admin/runs HTTP/1.1" 200 OK
INFO: 127.0.0.1:51778 - "GET /v1/admin/players/stats HTTP/1.1" 200 OK
INFO: 127.0.0.1:51780 - "GET /v1/admin/runs HTTP/1.1" 200 OK
INFO: 127.0.0.1:51779 - "GET /v1/admin/players/global HTTP/1.1" 200 OK
INFO: 127.0.0.1:51782 - "GET /v1/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588/players HTTP/1.1" 200 OK
INFO: 127.0.0.1:51784 - "DELETE /v1/admin/players/99386971-2d82-4513-a3ff-d4f17ac6e46c HTTP/1.1" 204 No Content
INFO: 127.0.0.1:51784 - "GET /v1/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588/players HTTP/1.1" 200 OK
INFO: 127.0.0.1:51784 - "GET /v1/admin/players/global HTTP/1.1" 200 OK
INFO: 127.0.0.1:51785 - "POST /v1/admin/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588/players HTTP/1.1" 201 Created
INFO: 127.0.0.1:51785 - "GET /v1/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588/players HTTP/1.1" 200 OK
INFO: 127.0.0.1:51788 - "GET /v1/admin/stats HTTP/1.1" 404 Not Found
INFO: 127.0.0.1:51789 - "GET /v1/admin/connections HTTP/1.1" 404 Not Found
INFO: 127.0.0.1:51790 - "GET /health HTTP/1.1" 200 OK
INFO: 127.0.0.1:51791 - "GET /ready HTTP/1.1" 200 OK
INFO: 127.0.0.1:51792 - "GET /dashboard HTTP/1.1" 200 OK
INFO: 127.0.0.1:51792 - "GET /static/css/styles.css HTTP/1.1" 200 OK
INFO: 127.0.0.1:51793 - "GET /static/js/utils.js HTTP/1.1" 200 OK
INFO: 127.0.0.1:51794 - "GET /static/js/websocket.js HTTP/1.1" 200 OK
INFO: 127.0.0.1:51795 - "GET /static/js/admin.js HTTP/1.1" 200 OK
INFO: 127.0.0.1:51796 - "GET /static/js/dashboard.js HTTP/1.1" 200 OK
INFO: 127.0.0.1:51796 - "GET /v1/runs/720fcd99-d7fe-4e53-8377-6688de0b718f HTTP/1.1" 404 Not Found
INFO: 127.0.0.1:51797 - "GET /v1/runs/720fcd99-d7fe-4e53-8377-6688de0b718f/players HTTP/1.1" 404 Not Found
INFO: 127.0.0.1:51942 - "GET /v1/runs/720fcd99-d7fe-4e53-8377-6688de0b718f/players HTTP/1.1" 404 Not Found
INFO: 127.0.0.1:51946 - "GET /v1/runs/720fcd99-d7fe-4e53-8377-6688de0b718f/players HTTP/1.1" 404 Not Found
INFO: 127.0.0.1:51947 - "GET /v1/admin/runs HTTP/1.1" 200 OK
INFO: 127.0.0.1:51948 - "GET /js/utils.js?v=1755895727560 HTTP/1.1" 200 OK
INFO: 127.0.0.1:51948 - "GET /js/admin-panel.js?v=1755895727560 HTTP/1.1" 200 OK
INFO: 127.0.0.1:51948 - "GET /v1/admin/runs HTTP/1.1" 200 OK
INFO: 127.0.0.1:51948 - "GET /health HTTP/1.1" 200 OK
INFO: 127.0.0.1:51949 - "GET /ready HTTP/1.1" 200 OK
INFO: 127.0.0.1:51952 - "GET /dashboard?api=http%3A%2F%2F127.0.0.1%3A8000&run=19dae986-3989-41ae-9f32-ea6ac8eaa588 HTTP/1.1" 200 OK
INFO: 127.0.0.1:51952 - "GET /v1/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588 HTTP/1.1" 200 OK
INFO: 127.0.0.1:51952 - "GET /v1/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588/players HTTP/1.1" 200 OK
INFO: 127.0.0.1:51952 - "GET /v1/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588/encounters?limit=20 HTTP/1.1" 200 OK
INFO: 127.0.0.1:51952 - "GET /v1/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588/links HTTP/1.1" 200 OK
INFO: 127.0.0.1:51952 - "GET /v1/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588/blocklist HTTP/1.1" 200 OK
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed - both session token and legacy Bearer token invalid: session_error=Invalid or expired session token, bearer_error=Invalid or expired token
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed (HTTP 401): Invalid or expired token
INFO: 127.0.0.1:51953 - "WebSocket /v1/ws?run_id=19dae986-3989-41ae-9f32-ea6ac8eaa588&token=ZhH92NGASUdJiZrJGbxmnKA_TEU7HANF" 403
INFO: connection rejected (403 Forbidden)
INFO: connection closed
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed - both session token and legacy Bearer token invalid: session_error=Invalid or expired session token, bearer_error=Invalid or expired token
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed (HTTP 401): Invalid or expired token
INFO: 127.0.0.1:51954 - "WebSocket /v1/ws?run_id=19dae986-3989-41ae-9f32-ea6ac8eaa588&token=ZhH92NGASUdJiZrJGbxmnKA_TEU7HANF" 403
INFO: connection rejected (403 Forbidden)
INFO: connection closed
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed - both session token and legacy Bearer token invalid: session_error=Invalid or expired session token, bearer_error=Invalid or expired token
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed (HTTP 401): Invalid or expired token
INFO: 127.0.0.1:51955 - "WebSocket /v1/ws?run_id=19dae986-3989-41ae-9f32-ea6ac8eaa588&token=ZhH92NGASUdJiZrJGbxmnKA_TEU7HANF" 403
INFO: connection rejected (403 Forbidden)
INFO: connection closed
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed - both session token and legacy Bearer token invalid: session_error=Invalid or expired session token, bearer_error=Invalid or expired token
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed (HTTP 401): Invalid or expired token
INFO: 127.0.0.1:51956 - "WebSocket /v1/ws?run_id=19dae986-3989-41ae-9f32-ea6ac8eaa588&token=ZhH92NGASUdJiZrJGbxmnKA_TEU7HANF" 403
INFO: connection rejected (403 Forbidden)
INFO: connection closed
INFO: 127.0.0.1:51957 - "GET /js/utils.js?v=1755895754341 HTTP/1.1" 200 OK
INFO: 127.0.0.1:51957 - "GET /js/admin-panel.js?v=1755895754341 HTTP/1.1" 200 OK
INFO: 127.0.0.1:51957 - "GET /v1/admin/runs HTTP/1.1" 200 OK
INFO: 127.0.0.1:51957 - "GET /health HTTP/1.1" 200 OK
INFO: 127.0.0.1:51958 - "GET /ready HTTP/1.1" 200 OK
INFO: 127.0.0.1:51962 - "GET /v1/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588/players HTTP/1.1" 200 OK
INFO: 127.0.0.1:51961 - "GET /v1/admin/players/global HTTP/1.1" 200 OK
INFO: 127.0.0.1:51959 - "GET /v1/admin/players/stats HTTP/1.1" 200 OK
INFO: 127.0.0.1:51960 - "GET /v1/admin/runs HTTP/1.1" 200 OK
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed - both session token and legacy Bearer token invalid: session_error=Invalid or expired session token, bearer_error=Invalid or expired token
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed (HTTP 401): Invalid or expired token
INFO: 127.0.0.1:51964 - "WebSocket /v1/ws?run_id=19dae986-3989-41ae-9f32-ea6ac8eaa588&token=ZhH92NGASUdJiZrJGbxmnKA_TEU7HANF" 403
INFO: connection rejected (403 Forbidden)
INFO: connection closed
INFO: 127.0.0.1:51960 - "DELETE /v1/admin/players/66adc11d-ad6e-4a5c-bdf8-4a92b8f5693e HTTP/1.1" 204 No Content
INFO: 127.0.0.1:51960 - "GET /v1/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588/players HTTP/1.1" 200 OK
INFO: 127.0.0.1:51960 - "GET /v1/admin/players/global HTTP/1.1" 200 OK
INFO: 127.0.0.1:51965 - "POST /v1/admin/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588/players HTTP/1.1" 201 Created
INFO: 127.0.0.1:51965 - "GET /v1/runs/19dae986-3989-41ae-9f32-ea6ac8eaa588/players HTTP/1.1" 200 OK
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed - both session token and legacy Bearer token invalid: session_error=Invalid or expired session token, bearer_error=Invalid or expired token
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed (HTTP 401): Invalid or expired token
INFO: 127.0.0.1:51966 - "WebSocket /v1/ws?run_id=19dae986-3989-41ae-9f32-ea6ac8eaa588&token=ZhH92NGASUdJiZrJGbxmnKA_TEU7HANF" 403
INFO: connection rejected (403 Forbidden)
INFO: connection closed
INFO: 127.0.0.1:51967 - "GET /v1/runs/720fcd99-d7fe-4e53-8377-6688de0b718f HTTP/1.1" 404 Not Found
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed - both session token and legacy Bearer token invalid: session_error=Invalid or expired session token, bearer_error=Invalid or expired token
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed (HTTP 401): Invalid or expired token
INFO: 127.0.0.1:51973 - "WebSocket /v1/ws?run_id=19dae986-3989-41ae-9f32-ea6ac8eaa588&token=ZhH92NGASUdJiZrJGbxmnKA_TEU7HANF" 403
INFO: connection rejected (403 Forbidden)
INFO: connection closed
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed - both session token and legacy Bearer token invalid: session_error=Invalid or expired session token, bearer_error=Invalid or expired token
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed (HTTP 401): Invalid or expired token
INFO: 127.0.0.1:51999 - "WebSocket /v1/ws?run_id=19dae986-3989-41ae-9f32-ea6ac8eaa588&token=ZhH92NGASUdJiZrJGbxmnKA_TEU7HANF" 403
INFO: connection rejected (403 Forbidden)
INFO: connection closed
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed - both session token and legacy Bearer token invalid: session_error=Invalid or expired session token, bearer_error=Invalid or expired token
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed (HTTP 401): Invalid or expired token
INFO: 127.0.0.1:52007 - "WebSocket /v1/ws?run_id=19dae986-3989-41ae-9f32-ea6ac8eaa588&token=ZhH92NGASUdJiZrJGbxmnKA_TEU7HANF" 403
INFO: connection rejected (403 Forbidden)
INFO: connection closed
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed - both session token and legacy Bearer token invalid: session_error=Invalid or expired session token, bearer_error=Invalid or expired token
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed (HTTP 401): Invalid or expired token
INFO: 127.0.0.1:52012 - "WebSocket /v1/ws?run_id=19dae986-3989-41ae-9f32-ea6ac8eaa588&token=ZhH92NGASUdJiZrJGbxmnKA_TEU7HANF" 403
INFO: connection rejected (403 Forbidden)
INFO: connection closed
INFO: 127.0.0.1:52018 - "GET /dashboard HTTP/1.1" 200 OK
INFO: 127.0.0.1:52018 - "GET /v1/runs/720fcd99-d7fe-4e53-8377-6688de0b718f HTTP/1.1" 404 Not Found
WARNING:soullink_tracker.api.websockets:WebSocket authentication failed - both session token and legac