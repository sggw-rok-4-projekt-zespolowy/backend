# Backend

WIP - Mocno

# Lokalne uruchmienie backendu

Instrukcje na Linux. na Windowsie pewnie podobnie. Potem sprawdzę, jak konkretnie.

0. `git pull https://github.com/sggw-rok-4-projekt-zespolowy/backend`
1. `python -m venv venv`
2. `source venv/bin/activate`
3. `pip install -r requirements.txt`
3. `python -m app.initialize_database`
4. `fastapi dev`

Potem można ściągnąć repo frontendu i uruchomić je przez `npm install` a potem `npm run dev` i powinno jakoś działać.
