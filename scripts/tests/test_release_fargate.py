"""Release ordering and failure handling, with AWS mocked (no account required)."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "release_fargate", Path(__file__).resolve().parents[1] / "release_fargate.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
IMAGE = "ghcr.io/phanmanhtan/cutlink@sha256:" + "a" * 64


class ReleaseTests(unittest.TestCase):
    def run_release(
        self, migration_exit=0, migration_start=True, active=False, rolled_back=False
    ):
        calls = []
        descriptions = 0

        def fake(*args, payload=None):
            nonlocal descriptions
            calls.append((args, payload))
            if args[:2] == ("cloudformation", "describe-stacks"):
                outputs = {
                    "ClusterArn": "cluster",
                    "ServiceName": "service",
                    "MigrationTaskArn": "migration:1",
                    "PrivateSubnets": "subnet-a,subnet-b",
                    "TaskSecurityGroup": "sg-task",
                    "TargetGroupArn": "target",
                }
                return {
                    "Stacks": [
                        {
                            "Outputs": [
                                {"OutputKey": k, "OutputValue": v}
                                for k, v in outputs.items()
                            ]
                        }
                    ]
                }
            if args[:2] == ("ecs", "describe-services"):
                descriptions += 1
                return {
                    "services": [
                        {
                            "taskDefinition": "new-app:2"
                            if descriptions == 3 and not rolled_back
                            else "app:1",
                            "desiredCount": 1,
                            "runningCount": 0 if descriptions == 2 else 1,
                            "pendingCount": 0,
                            "deployments": [
                                {
                                    "rolloutState": "IN_PROGRESS"
                                    if active
                                    else "COMPLETED"
                                }
                            ],
                        }
                    ]
                }
            if args[:2] == ("ecs", "describe-task-definition"):
                names = (
                    ["migration"]
                    if args[-1] == "migration:1"
                    else ["api", "worker", "beat", "redis"]
                )
                return {
                    "taskDefinition": {
                        "family": "migration" if names == ["migration"] else "app",
                        "taskDefinitionArn": args[-1],
                        "revision": 1,
                        "status": "ACTIVE",
                        "containerDefinitions": [
                            {
                                "name": n,
                                "image": "redis:7-alpine" if n == "redis" else "old",
                            }
                            for n in names
                        ],
                        "executionRoleArn": "execution-role",
                    }
                }
            if args[:2] == ("ecs", "register-task-definition"):
                return {
                    "taskDefinition": {
                        "taskDefinitionArn": "new-" + payload["family"] + ":2"
                    }
                }
            if args[:2] == ("ecs", "list-tasks"):
                return {"taskArns": ["old-task"]}
            if args[:2] == ("ecs", "run-task"):
                return (
                    {"tasks": [{"taskArn": "migration-task"}]}
                    if migration_start
                    else {"failures": [{}]}
                )
            if args[:2] == ("ecs", "describe-tasks"):
                container = {"name": "migration"}
                if migration_exit is not None:
                    container["exitCode"] = migration_exit
                return {"tasks": [{"containers": [container]}]}
            if args[:2] == ("elbv2", "describe-target-health"):
                return {
                    "TargetHealthDescriptions": [{"TargetHealth": {"State": "healthy"}}]
                }
            return {}

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(release, "aws", side_effect=fake),
        ):
            state = Path(directory) / "state.json"
            try:
                result = release.release("base", "app", IMAGE, state)
            except RuntimeError:
                result = json.loads(state.read_text()) if state.exists() else None
        return calls, result

    def test_success_promotes_same_digest_only_after_migration(self):
        calls, state = self.run_release()
        self.assertEqual(state["status"], "healthy")
        self.assertEqual(state["previousTaskDefinition"], "app:1")
        registrations = [
            payload
            for args, payload in calls
            if args[:2] == ("ecs", "register-task-definition")
        ]
        for definition in registrations:
            self.assertNotIn("taskDefinitionArn", definition)
            for container in definition["containerDefinitions"]:
                self.assertEqual(
                    container["image"],
                    "redis:7-alpine" if container["name"] == "redis" else IMAGE,
                )
        migration_result = next(
            i
            for i, (args, _) in enumerate(calls)
            if args[:2] == ("ecs", "describe-tasks")
        )
        start = next(
            i
            for i, (args, _) in enumerate(calls)
            if "--desired-count" in args and args[-1] == "1"
        )
        self.assertLess(migration_result, start)
        stopped = next(
            i
            for i, (args, _) in enumerate(calls)
            if args[:3] == ("ecs", "wait", "tasks-stopped") and args[-1] == "old-task"
        )
        run = next(
            i for i, (args, _) in enumerate(calls) if args[:2] == ("ecs", "run-task")
        )
        self.assertLess(stopped, run)

    def test_failed_or_missing_migration_exit_never_starts_new_revision(self):
        for code in (1, None):
            with self.subTest(code=code):
                calls, state = self.run_release(migration_exit=code)
                self.assertEqual(state["status"], "migration_failed")
                self.assertFalse(
                    any(
                        "--desired-count" in args and args[-1] == "1"
                        for args, _ in calls
                    )
                )

    def test_failed_migration_launch_never_starts_new_revision(self):
        calls, state = self.run_release(migration_start=False)
        self.assertEqual(state["status"], "migration_failed")
        self.assertFalse(
            any("--desired-count" in args and args[-1] == "1" for args, _ in calls)
        )

    def test_refuses_overlap(self):
        calls, state = self.run_release(active=True)
        self.assertIsNone(state)
        self.assertFalse(
            any(args[:2] == ("ecs", "update-service") for args, _ in calls)
        )

    def test_detects_circuit_breaker_rollback(self):
        _, state = self.run_release(rolled_back=True)
        self.assertEqual(state["status"], "deployment_failed")

    def test_rejects_mutable_tag_before_aws(self):
        with patch.object(release, "aws") as aws, self.assertRaises(ValueError):
            release.release(
                "base", "app", "ghcr.io/phanmanhtan/cutlink:latest", Path("unused")
            )
        aws.assert_not_called()


if __name__ == "__main__":
    unittest.main()
