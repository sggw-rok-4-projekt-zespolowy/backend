# Backend

WIP - Mocno

# Lokalne uruchmienie backendu

Instrukcje na Linux. na Windowsie pewnie podobnie. Potem sprawdzę, jak konkretnie.

Za pierwszym razem:

0. `git clone https://github.com/sggw-rok-4-projekt-zespolowy/backend`
1. `cd backend`
2. `python -m venv venv`
3. `source venv/bin/activate`
4. `pip install -r requirements.txt`
5. `alembic upgrade head`
6. `python -m app.initialize_database`
7. `fastapi dev`
8. `python seed_tracks.py`

Kolejnym razem (w katalogu backend):
0. `source venv/bin/activate`
1. `fastapi dev`

Potem można ściągnąć repo frontendu i uruchomić je przez `npm install` a potem `npm run dev` i powinno jakoś działać.
