import logging

from fasjson_client import Client as FasjsonClient
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.types import ASGIApp

from ..core.config import get_settings
from ..database import init_async_model
from ..database.model import Destination, Filter, GenerationRule, Rule, TrackingRule, User
from . import api_models
from .auth import Identity, get_identity
from .database import gen_db_session
from .fasjson import get_fasjson_client

log = logging.getLogger(__name__)


async def global_execution_handler(
    request: StarletteRequest, exc: Exception
) -> ASGIApp:  # pragma: no cover todo
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content="Unknown Error",
    )


app = FastAPI()


@app.on_event("startup")
def add_middlewares():
    app.add_middleware(
        ServerErrorMiddleware,
        handler=global_execution_handler,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins.split(" "),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.on_event("startup")
async def init_model():
    await init_async_model()


@app.get("/users/", response_model=list[str])
def get_users(
    search: str, fasjson_client: FasjsonClient = Depends(get_fasjson_client)
):  # pragma: no cover todo
    return [u["username"] for u in fasjson_client.search(username=search).result]


@app.get("/user/{username}/", response_model=api_models.User)
async def get_user(username, db_session: AsyncSession = Depends(gen_db_session)):
    user = await User.async_get_or_create(db_session, name=username)
    return user


@app.get("/user/{username}/info")
def get_user_info(
    username, fasjson_client: FasjsonClient = Depends(get_fasjson_client)
):  # pragma: no cover todo
    return fasjson_client.get_user(username=username).result


@app.get("/user/{username}/groups")
def get_user_groups(username, fasjson_client: FasjsonClient = Depends(get_fasjson_client)):
    return [g["groupname"] for g in fasjson_client.list_user_groups(username=username).result]


@app.get("/user/{username}/destinations", response_model=list[api_models.Destination])
def get_user_destinations(
    username, fasjson_client: FasjsonClient = Depends(get_fasjson_client)
):  # pragma: no cover todo
    user = fasjson_client.get_user(username=username).result
    result = [{"protocol": "email", "address": email} for email in user["emails"]]
    for nick in user.get("ircnicks", []):
        address = nick.split(":", 1)[1] if ":" in nick else nick
        if nick.startswith("matrix:"):
            protocol = "matrix"
        else:
            protocol = "irc"
        result.append({"protocol": protocol, "address": address})
    return result


@app.get("/user/{username}/rules", response_model=list[api_models.Rule])
async def get_user_rules(
    username,
    identity: Identity = Depends(get_identity),
    db_session: AsyncSession = Depends(gen_db_session),
):
    if username != identity.name:
        raise HTTPException(status_code=403, detail="Not allowed to see someone else's rules")

    db_result = await db_session.execute(Rule.select_related().filter(Rule.user.has(name=username)))
    return db_result.scalars().all()


@app.get("/user/{username}/rules/{id}", response_model=api_models.Rule)
async def get_user_rule(
    username: str,
    id: int,
    identity: Identity = Depends(get_identity),
    db_session: AsyncSession = Depends(gen_db_session),
):
    if username != identity.name:
        raise HTTPException(status_code=403, detail="Not allowed to see someone else's rules")

    return (
        await db_session.execute(
            Rule.select_related().filter(Rule.id == id, Rule.user.has(name=username))
        )
    ).scalar_one()


@app.put("/user/{username}/rules/{id}", response_model=api_models.Rule)
async def edit_user_rule(
    username: str,
    id: int,
    rule: api_models.Rule,
    identity: Identity = Depends(get_identity),
    db_session: AsyncSession = Depends(gen_db_session),
):
    if username != identity.name:
        raise HTTPException(status_code=403, detail="Not allowed to edit someone else's rules")

    rule_db = (
        await db_session.execute(
            Rule.select_related().filter(Rule.id == id, Rule.user.has(name=username))
        )
    ).scalar_one()
    rule_db.name = rule.name
    rule_db.tracking_rule.name = rule.tracking_rule.name
    rule_db.tracking_rule.params = rule.tracking_rule.params
    for to_delete in rule_db.generation_rules[len(rule.generation_rules) :]:
        await db_session.delete(to_delete)
    for index, gr in enumerate(rule.generation_rules):
        try:
            gr_db = rule_db.generation_rules[index]
        except IndexError:
            gr_db = GenerationRule(rule=rule_db)
            rule_db.generation_rules.append(gr_db)
        for to_delete in gr_db.destinations[len(gr.destinations) :]:
            await db_session.delete(to_delete)
        for index, dst in enumerate(gr.destinations):
            try:
                dst_db = gr_db.destinations[index]
            except IndexError:
                dst_db = Destination(
                    generation_rule=gr_db, protocol=dst.protocol, address=dst.address
                )
                gr_db.destinations.append(dst_db)
            else:
                dst_db.protocol = dst.protocol
                dst_db.address = dst.address
        to_delete = [f for f in gr_db.filters if f.name not in gr.filters.dict(exclude_unset=True)]
        for f in to_delete:
            await db_session.delete(f)
        existing_filters = {f.name: f for f in gr_db.filters}
        for f_name, f_params in gr.filters.dict(exclude_unset=True).items():
            try:
                f_db = existing_filters[f_name]
            except KeyError:
                f_db = Filter(generation_rule=gr_db, name=f_name, params=f_params)
                gr_db.filters.append(f_db)
            else:
                f_db.name = f_name
                f_db.params = f_params
        await db_session.flush()

    # TODO: emit a fedmsg

    # Refresh using the full query to get relationships
    return (
        await db_session.execute(
            Rule.select_related().filter(Rule.id == id, Rule.user.has(name=username))
        )
    ).scalar_one()


@app.delete("/user/{username}/rules/{id}")
async def delete_user_rule(
    username: str,
    id: int,
    identity: Identity = Depends(get_identity),
    db_session: AsyncSession = Depends(gen_db_session),
):
    if username != identity.name:
        raise HTTPException(status_code=403, detail="Not allowed to delete someone else's rules")

    rule = await Rule.async_get(db_session, id=id)
    await db_session.delete(rule)
    await db_session.flush()

    # TODO: emit a fedmsg


@app.post("/user/{username}/rules", response_model=api_models.Rule)
async def create_user_rule(
    username,
    rule: api_models.Rule,
    identity: Identity = Depends(get_identity),
    db_session: AsyncSession = Depends(gen_db_session),
):
    if username != identity.name:
        raise HTTPException(status_code=403, detail="Not allowed to edit someone else's rules")
    log.info("Creating rule:", rule)
    user = await User.async_get_or_create(db_session, name=username)
    rule_db = Rule(user=user, name=rule.name)
    db_session.add(rule_db)
    await db_session.flush()
    tr = TrackingRule(rule=rule_db, name=rule.tracking_rule.name, params=rule.tracking_rule.params)
    db_session.add(tr)
    await db_session.flush()
    for generation_rule in rule.generation_rules:
        gr = GenerationRule(rule=rule_db)
        db_session.add(gr)
        await db_session.flush()
        for destination in generation_rule.destinations:
            db_session.add(
                Destination(
                    generation_rule=gr, protocol=destination.protocol, address=destination.address
                )
            )
        for name, params in generation_rule.filters.dict().items():
            db_session.add(Filter(generation_rule=gr, name=name, params=params))
        await db_session.flush()

    # TODO: emit a fedmsg

    # Refresh using the full query to get relationships
    return (
        await db_session.execute(
            Rule.select_related().filter(Rule.id == rule_db.id, Rule.user.has(name=username))
        )
    ).scalar_one()


@app.get("/applications", response_model=list[str])
def get_applications():
    # TODO: Read the installed schemas and extract the applications. Return sorted, please :-)
    return [
        "anitya",
        "bodhi",
        "koji",
    ]


@app.get("/artifacts/owned", response_model=list[dict[str, str]])
def get_owned_artifacts(
    users: list[str] = Query(default=[]), groups: list[str] = Query(default=[])
):
    # TODO: Get artifacts owned by a user or a group

    artifacts = []
    artifact_names = []

    def _add_artifact(a):
        if a["name"] in artifact_names:
            return
        artifacts.append(a)
        artifact_names.append(a["name"])

    for username in users or []:
        # Add artifacts owned by the user to the list
        _add_artifact({"type": "rpm", "name": "foobar-user-owned"})
    for groupname in groups or []:
        # Add artifacts owned by the user to the list
        _add_artifact({"type": "rpm", "name": "foobar-group-owned"})
    artifacts.sort(key=lambda a: a["name"])
    return artifacts
