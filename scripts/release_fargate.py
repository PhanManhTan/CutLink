"""Release an existing image to provisioned Fargate infrastructure using AWS CLI v2."""

import argparse
import copy
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

IMAGE_PATTERN = r"ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}"
REGISTER_FIELDS = {
    "family",
    "taskRoleArn",
    "executionRoleArn",
    "networkMode",
    "containerDefinitions",
    "volumes",
    "placementConstraints",
    "requiresCompatibilities",
    "cpu",
    "memory",
    "pidMode",
    "ipcMode",
    "proxyConfiguration",
    "inferenceAccelerators",
    "ephemeralStorage",
    "runtimePlatform",
    "enableFaultInjection",
}


def aws(*arguments, payload=None):
    with tempfile.TemporaryDirectory(prefix="cutlink-release-") as directory:
        command = ["aws", *arguments, "--output", "json", "--no-cli-pager"]
        if payload is not None:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            command += ["--cli-input-json", f"file://{path}"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(
            f"AWS {' '.join(arguments[:2])} failed: {result.stderr.strip()}"
        )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def stack_outputs(name):
    result = aws("cloudformation", "describe-stacks", "--stack-name", name)
    return {
        item["OutputKey"]: item["OutputValue"]
        for item in result["Stacks"][0]["Outputs"]
    }


def definition_with_image(original, names, image):
    definition = copy.deepcopy(
        {key: val for key, val in original.items() if key in REGISTER_FIELDS}
    )
    found = set()
    for container in definition["containerDefinitions"]:
        if container["name"] in names:
            container["image"] = image
            found.add(container["name"])
    if found != set(names):
        raise RuntimeError(
            f"Task definition is missing containers: {set(names) - found}"
        )
    return definition


def release(base_stack, app_stack, image, state_path):
    if not re.fullmatch(IMAGE_PATTERN, image):
        raise ValueError("Use a GHCR image pinned by sha256 digest, not a mutable tag")
    base, app = stack_outputs(base_stack), stack_outputs(app_stack)
    cluster, service_name = base["ClusterArn"], app["ServiceName"]

    def service():
        response = aws(
            "ecs", "describe-services", "--cluster", cluster, "--services", service_name
        )
        if response.get("failures") or len(response.get("services", [])) != 1:
            raise RuntimeError("Application service was not found")
        return response["services"][0]

    current = service()
    if current["desiredCount"] not in (0, 1):
        raise RuntimeError("This release flow supports the single-task demo only")
    if current.get("pendingCount", 0) or any(
        deployment.get("rolloutState") == "IN_PROGRESS"
        for deployment in current.get("deployments", [])
    ):
        raise RuntimeError("Another ECS deployment is still in progress")
    old_arn = current["taskDefinition"]
    old = aws("ecs", "describe-task-definition", "--task-definition", old_arn)[
        "taskDefinition"
    ]
    migration = aws(
        "ecs", "describe-task-definition", "--task-definition", app["MigrationTaskArn"]
    )["taskDefinition"]
    app_definition = definition_with_image(old, {"api", "worker", "beat"}, image)
    migration_definition = definition_with_image(migration, {"migration"}, image)
    state = {
        "baseStack": base_stack,
        "appStack": app_stack,
        "cluster": cluster,
        "service": service_name,
        "previousTaskDefinition": old_arn,
        "previousDesiredCount": current["desiredCount"],
        "image": image,
        "status": "prepared",
    }

    def save(status):
        state["status"] = status
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    save("prepared")
    app_arn = aws("ecs", "register-task-definition", payload=app_definition)[
        "taskDefinition"
    ]["taskDefinitionArn"]
    migration_arn = aws(
        "ecs", "register-task-definition", payload=migration_definition
    )["taskDefinition"]["taskDefinitionArn"]
    state.update(newTaskDefinition=app_arn, migrationTaskDefinition=migration_arn)
    old_tasks = aws(
        "ecs",
        "list-tasks",
        "--cluster",
        cluster,
        "--service-name",
        service_name,
        "--desired-status",
        "RUNNING",
    )["taskArns"]
    aws(
        "ecs",
        "update-service",
        "--cluster",
        cluster,
        "--service",
        service_name,
        "--desired-count",
        "0",
    )
    aws(
        "ecs",
        "wait",
        "services-stable",
        "--cluster",
        cluster,
        "--services",
        service_name,
    )
    if old_tasks:
        aws("ecs", "wait", "tasks-stopped", "--cluster", cluster, "--tasks", *old_tasks)
    stopped = service()
    if stopped["runningCount"] or stopped["pendingCount"]:
        raise RuntimeError("Previous release has not stopped")
    save("stopped")
    network = {
        "awsvpcConfiguration": {
            "subnets": base["PrivateSubnets"].split(","),
            "securityGroups": [base["TaskSecurityGroup"]],
            "assignPublicIp": "DISABLED",
        }
    }
    result = aws(
        "ecs",
        "run-task",
        payload={
            "cluster": cluster,
            "taskDefinition": migration_arn,
            "launchType": "FARGATE",
            "platformVersion": "1.4.0",
            "networkConfiguration": network,
        },
    )
    if result.get("failures") or len(result.get("tasks", [])) != 1:
        save("migration_failed")
        raise RuntimeError(
            "Migration task could not start; application remains stopped"
        )
    task_arn = result["tasks"][0]["taskArn"]
    state["migrationTask"] = task_arn
    save("migrating")
    aws("ecs", "wait", "tasks-stopped", "--cluster", cluster, "--tasks", task_arn)
    result = aws("ecs", "describe-tasks", "--cluster", cluster, "--tasks", task_arn)
    tasks = result.get("tasks", [])
    containers = tasks[0].get("containers", []) if len(tasks) == 1 else []
    migrated = next((item for item in containers if item["name"] == "migration"), {})
    if result.get("failures") or migrated.get("exitCode") != 0:
        save("migration_failed")
        raise RuntimeError(
            f"Migration failed; application remains stopped. Inspect task {task_arn}"
        )
    save("migration_succeeded")
    # The only startup of a new application revision is below the successful exit-code check.
    aws(
        "ecs",
        "update-service",
        "--cluster",
        cluster,
        "--service",
        service_name,
        "--task-definition",
        app_arn,
        "--desired-count",
        "1",
    )
    save("deploying")
    aws(
        "ecs",
        "wait",
        "services-stable",
        "--cluster",
        cluster,
        "--services",
        service_name,
    )
    # ECS's stable waiter can precede the first healthy ALB probe on a stopped service.
    deadline = time.monotonic() + 180
    while True:
        deployed = service()
        if deployed["taskDefinition"] != app_arn:
            save("deployment_failed")
            raise RuntimeError(
                "Expected application revision changed; check ECS circuit breaker"
            )
        health = aws(
            "elbv2",
            "describe-target-health",
            "--target-group-arn",
            base["TargetGroupArn"],
        )
        if deployed["runningCount"] == 1 and any(
            item["TargetHealth"]["State"] == "healthy"
            for item in health.get("TargetHealthDescriptions", [])
        ):
            break
        if time.monotonic() >= deadline:
            save("deployment_failed")
            raise RuntimeError(
                "ALB did not report a database-ready target within 180 seconds"
            )
        time.sleep(5)
    save("healthy")
    print(f"Released {image} to {service_name}; ALB target is healthy.")
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-stack", required=True)
    parser.add_argument("--app-stack", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument(
        "--state", type=Path, default=Path(".deploy/fargate-release.json")
    )
    args = parser.parse_args()
    release(args.base_stack, args.app_stack, args.image, args.state)


if __name__ == "__main__":
    main()
