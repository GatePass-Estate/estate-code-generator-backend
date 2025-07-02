from fastapi import APIRouter, Depends
from app.schemas.auth import LoginRequest, LoginResponse
from app.repositories.user import UserRepository
from app.services.auth import generate_access_token
from app.libs.http_handler import get_http_handler, AsyncHttpHandler

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login_user(
    request: LoginRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> LoginResponse:
    """
    Authenticates a user using email and password, and returns a JWT token.
    """
    repo = UserRepository(ahttp_client)
    user = await repo.authenticate_user(request.email, request.password)
    token = generate_access_token(user)
    return LoginResponse(success=True, role=user["role"], access_token=token)
