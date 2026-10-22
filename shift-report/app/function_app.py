"""Deploy the same package twice, with disjoint APP_KIND identities."""

import functools
import json
import logging
import os
from azure.core.exceptions import AzureError

import azure.functions as func

from adapters import AzureStore, JobQueue, Mailer, Sources, credential
from automation import automation_status
from domain import ControlledError, Settings, canonical, utcnow
from runtime import Runtime

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
KIND = os.environ.get("APP_KIND", "")


@functools.lru_cache(maxsize=1)
def runtime():
    settings = Settings.load()
    identity = credential()
    store = AzureStore(settings, identity)
    if settings.kind == "producer":
        return Runtime(settings, store, Sources(settings, identity), JobQueue(settings, identity))
    return Runtime(settings, store, mailer=Mailer(settings, identity))


def respond(action, status=200):
    try:
        return func.HttpResponse(canonical(action()), status_code=status, mimetype="application/json")
    except (ValueError, KeyError, TypeError):
        return func.HttpResponse('{"error":"Invalid request"}', status_code=400, mimetype="application/json")
    except ControlledError as error:
        return func.HttpResponse(canonical({"error": str(error)}), status_code=409, mimetype="application/json")
    except (AzureError, RuntimeError) as error:
        logging.error("HTTP runtime failure type=%s", type(error).__name__)
        return func.HttpResponse('{"error":"Runtime failure; inspect durable status"}',
                                 status_code=500, mimetype="application/json")


@app.route(route="automation", methods=["GET"])
def automation(req: func.HttpRequest) -> func.HttpResponse:
    try:
        result = automation_status(Settings.load(), utcnow())
        return func.HttpResponse(canonical(result),
                                 status_code=409 if result["status"] == "InvalidPolicy" else 200,
                                 mimetype="application/json",
                                 headers={"Cache-Control": "no-store"})
    except ValueError:
        return func.HttpResponse('{"status":"InvalidConfiguration","error":"Invalid automation settings"}',
                                 status_code=409, mimetype="application/json")


if KIND == "producer":
    @app.route(route="connectivity", methods=["GET"])
    def connectivity(req: func.HttpRequest) -> func.HttpResponse:
        return respond(lambda: runtime().sources.access_proof())

    @app.route(route="prepare", methods=["POST"])
    def prepare(req: func.HttpRequest) -> func.HttpResponse:
        return respond(lambda: runtime().prepare(req.get_json()), 202)

    @app.route(route="status", methods=["GET"])
    def status(req: func.HttpRequest) -> func.HttpResponse:
        return respond(lambda: runtime().status(req.params.get("reportId")))

    @app.queue_trigger(arg_name="message", queue_name="hv-report-jobs", connection="REPORT_QUEUE")
    def generate(message: func.QueueMessage):
        # Exceptions must escape so host records failure; no success fallback.
        runtime().generate(json.loads(message.get_body().decode("utf-8")))

    @app.timer_trigger(schedule="0 50 6,14,22 * * *", arg_name="timer", run_on_startup=False,
                       use_monitor=True)
    def preflight(timer: func.TimerRequest):
        runtime().preflight(timer.past_due)

    @app.timer_trigger(schedule="0 55 6,14,22 * * *", arg_name="timer", run_on_startup=False,
                       use_monitor=True)
    def collect(timer: func.TimerRequest):
        runtime().collection_tick(timer.past_due)

elif KIND == "dispatcher":
    @app.route(route="artifact", methods=["GET"])
    def artifact(req: func.HttpRequest) -> func.HttpResponse:
        def download():
            data, attachment = runtime().artifact(req.params.get("reportId"), req.params.get("filename"))
            return func.HttpResponse(
                data, status_code=200, mimetype=attachment["contentType"],
                headers={
                    "Content-Disposition": 'attachment; filename="' + attachment["name"] + '"',
                    "X-Content-SHA256": attachment["sha256"],
                    "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                },
            )
        try:
            return download()
        except (ValueError, KeyError, TypeError):
            return func.HttpResponse('{"error":"Invalid artifact request"}', status_code=400,
                                     mimetype="application/json")
        except ControlledError as error:
            return func.HttpResponse(canonical({"error": str(error)}), status_code=409,
                                     mimetype="application/json")

    @app.route(route="preview", methods=["GET"])
    def preview(req: func.HttpRequest) -> func.HttpResponse:
        return respond(lambda: runtime().preview(req.params.get("reportId")))

    @app.route(route="dispatch", methods=["POST"])
    def dispatch(req: func.HttpRequest) -> func.HttpResponse:
        def invoke():
            body = req.get_json()
            if not isinstance(body, dict) or set(body) != {"reportId"}:
                raise ValueError("Only reportId is accepted")
            return runtime().dispatch(body["reportId"])
        return respond(invoke)

    @app.route(route="status", methods=["GET"])
    def status(req: func.HttpRequest) -> func.HttpResponse:
        return respond(lambda: runtime().status(req.params.get("reportId")))

    @app.timer_trigger(schedule="0 0 7,15,23 * * *", arg_name="timer", run_on_startup=False,
                       use_monitor=True)
    def dispatch_cycle(timer: func.TimerRequest):
        runtime().dispatch_tick(timer.past_due)
