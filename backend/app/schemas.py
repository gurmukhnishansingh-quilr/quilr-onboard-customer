from pydantic import BaseModel, Field, EmailStr


class InstanceBase(BaseModel):
    name: str = Field(..., min_length=1)
    bff_url: str | None = None
    status: str | None = "active"
    pg_host: str | None = None
    pg_port: str | None = None
    pg_user: str | None = None
    pg_password: str | None = None
    neo4j_host: str | None = None
    neo4j_port: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None


class InstanceCreate(InstanceBase):
    pass


class InstanceUpdate(BaseModel):
    name: str | None = None
    bff_url: str | None = None
    status: str | None = None
    pg_host: str | None = None
    pg_port: str | None = None
    pg_user: str | None = None
    pg_password: str | None = None
    neo4j_host: str | None = None
    neo4j_port: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None


class InstanceOut(InstanceBase):
    id: str
    created_at: str
    updated_at: str


class CustomerBase(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    first_name: str | None = None
    last_name: str | None = None
    department: str | None = None
    vendor: str | None = None
    contact_email: EmailStr | None = None
    instance_id: str | None = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    department: str | None = None
    vendor: str | None = None
    contact_email: EmailStr | None = None
    instance_id: str | None = None


class CustomerOut(CustomerBase):
    id: str
    created_at: str
    updated_at: str
    instance_name: str | None = None
    tenant_name: str | None = None
    tenant_id: str | None = None
    subscriber: str | None = None


class InternalUserOut(BaseModel):
    id: str | None = None
    name: str | None = None
    email: EmailStr | None = None
    account_type: str | None = None


class InternalUserPasswordUpdate(BaseModel):
    instance_id: str
    user_id: str
    tenant_id: str
    subscriber: str | None = None
    new_password: str = Field(..., min_length=8)


class InternalUserCreate(BaseModel):
    instance_id: str
    tenant_id: str | None = None
    subscriber: str | None = None
    match_name: str | None = None
    match_email: EmailStr | None = None
    account_type: str | None = None
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    email: EmailStr
    password: str | None = None


class SessionOut(BaseModel):
    authenticated: bool
    user: dict | None = None


class OnboardRequest(BaseModel):
    instance: InstanceCreate | None = None
    customer: CustomerCreate


class OnboardResponse(BaseModel):
    instance_id: str
    customer_id: str


class TokenExchangeRequest(BaseModel):
    id_token: str
    groups: list[str] | None = None


class PostgresTestRequest(BaseModel):
    instance_id: str | None = None
    host: str | None = None
    port: int | None = None
    user: str | None = None
    password: str | None = None
    database: str | None = None
    sslmode: str | None = None


class Neo4jTestRequest(BaseModel):
    instance_id: str | None = None
    host: str | None = None
    port: int | None = None
    user: str | None = None
    password: str | None = None
