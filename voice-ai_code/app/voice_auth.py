"""Authentication shared by the new voice endpoints."""
from fastapi import Cookie, Header, HTTPException
from jose import jwt, JWTError
from app.jwt_config import SECRET_KEY, ALGORITHM, ISSUER

def voice_identity(
    access_token: str | None = Cookie(None, alias="ACCESS_TOKEN"),
    authorization: str | None = Header(None),
):
    token = access_token
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() != "bearer" or not value:
            raise HTTPException(401, "로그인이 필요합니다.")
        token = value
    if not token:
        raise HTTPException(401, "로그인이 필요합니다.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM],
                             issuer=ISSUER, options={"require_exp": True})
        if not payload.get("sub"):
            raise JWTError("Missing subject")
    except JWTError:
        raise HTTPException(401, "로그인이 만료되었거나 유효하지 않습니다.")
    return {"id": str(payload["sub"]), "token": token}
