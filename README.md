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
8. `python seed_tracks.py` (w drugim terminalu, gdy backend uruchomiony, w katalogu backend)

Kolejnym razem (w katalogu backend):
0. `source venv/bin/activate`
1. `fastapi dev`

## Windows (PowerShell)

Wymagania: zainstalowany Python 3.13 (ta sama wersja co w Dockerfile) i Git. Polecenia wpisujemy w PowerShellu (np. terminal w VS Code).

Za pierwszym razem:

0. `git clone https://github.com/sggw-rok-4-projekt-zespolowy/backend`
1. `cd backend`
2. `python -m venv venv`
3. `.\venv\Scripts\Activate.ps1` (na początku linii powinno pojawić się `(venv)`)
4. `pip install -r requirements.txt`
5. `alembic upgrade head`
6. `python -m app.initialize_database`
7. `fastapi dev`
8. W drugim terminalu, w katalogu backend: `.\venv\Scripts\Activate.ps1`, a potem `python seed_tracks.py` (backend musi być uruchomiony)

Kolejnym razem (w katalogu backend):

0. `.\venv\Scripts\Activate.ps1`
1. `fastapi dev`

Możliwe problemy:

- **Krok 3: "running scripts is disabled on this system"**: jednorazowo wykonaj `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` i powtórz krok 3.
- **Używasz cmd zamiast PowerShella**: w kroku 3 wpisz `venv\Scripts\activate.bat`.
- **Używasz Git Basha**: w kroku 3 wpisz `source venv/Scripts/activate`.
- **Krok 5: "alembic is not recognized"**: krok 4 się nie powiódł albo venv nie jest aktywny (brak `(venv)` na początku linii). Aktywuj venv i powtórz krok 4.

Potem można ściągnąć repo frontendu i uruchomić je przez `npm install` a potem `npm run dev` i powinno jakoś działać.
