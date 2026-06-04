from flask import Flask, g

from .config import Config
from .database import SessionLocal, init_db
from .routes import alerts, auth, basemap, driver, map, overview, reports, rules, schedules, simulation, tasks, users, vehicles


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.before_request
    def open_session():
        g.db = SessionLocal()

    @app.teardown_request
    def close_session(exc=None):
        session = g.pop("db", None)
        if session is not None:
            if exc:
                session.rollback()
            session.close()

    @app.after_request
    def cors(resp):
        resp.headers["Access-Control-Allow-Origin"] = app.config["CORS_ALLOW_ORIGIN"]
        resp.headers["Access-Control-Allow-Headers"] = "Authorization,Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PATCH,DELETE,OPTIONS"
        return resp

    @app.get("/api/health")
    def health():
        return {"message": "ok", "data": {"service": "forklift-dispatch"}}

    app.register_blueprint(auth.bp)
    app.register_blueprint(basemap.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(overview.bp)
    app.register_blueprint(tasks.bp)
    app.register_blueprint(vehicles.bp)
    app.register_blueprint(driver.bp)
    app.register_blueprint(map.bp)
    app.register_blueprint(rules.bp)
    app.register_blueprint(schedules.bp)
    app.register_blueprint(alerts.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(simulation.bp)

    with app.app_context():
        init_db()

    return app
