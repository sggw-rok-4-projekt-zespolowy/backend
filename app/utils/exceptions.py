from fastapi import HTTPException

HTTPForbidden = HTTPException(status_code=403, detail="Forbidden")

HTTPUnauthorized = HTTPException(status_code=401, detail="Unauthorized")
