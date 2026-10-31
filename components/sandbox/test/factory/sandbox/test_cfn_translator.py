"""Property-based tests for CFN-to-LocalStack translator."""
from __future__ import annotations

import yaml
from hypothesis import given, settings, strategies as st

from factory.sandbox.runtime.cfn_translator import (
    is_supported, is_security_relevant, translate,
)

_SUPPORTED_TYPES = [
    "AWS::IAM::Role", "AWS::IAM::Policy", "AWS::Lambda::Function",
    "AWS::S3::Bucket", "AWS::DynamoDB::Table", "AWS::SQS::Queue",
    "AWS::SNS::Topic", "AWS::ApiGateway::RestApi", "AWS::SSM::Parameter",
    "AWS::KMS::Key", "AWS::SecretsManager::Secret",
]

_UNSUPPORTED_TYPES = [
    "AWS::EC2::Instance", "AWS::ECS::Service", "AWS::RDS::DBInstance",
    "AWS::Neptune::DBCluster", "AWS::ElastiCache::CacheCluster",
    "AWS::EKS::Cluster", "AWS::Redshift::Cluster",
]


class TestIsSupported:
    @settings(max_examples=30)
    @given(rtype=st.sampled_from(_SUPPORTED_TYPES))
    def test_supported_types_accepted(self, rtype: str) -> None:
        assert is_supported(rtype) is True

    @settings(max_examples=30)
    @given(rtype=st.sampled_from(_UNSUPPORTED_TYPES))
    def test_unsupported_types_rejected(self, rtype: str) -> None:
        assert is_supported(rtype) is False


class TestIsSecurityRelevant:
    @settings(max_examples=30)
    @given(rtype=st.sampled_from([
        "AWS::IAM::Role", "AWS::S3::BucketPolicy",
        "AWS::Lambda::Function", "AWS::DynamoDB::Table",
    ]))
    def test_security_types_accepted(self, rtype: str) -> None:
        assert is_security_relevant(rtype) is True

    def test_logs_not_security_relevant(self) -> None:
        assert is_security_relevant("AWS::Logs::LogGroup") is False


class TestTranslate:
    def _make_template(self, resources: dict) -> str:
        return yaml.dump({
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": resources,
        })

    def test_keeps_supported_drops_unsupported(self) -> None:
        tmpl = self._make_template({
            "MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {}},
            "MyEC2": {"Type": "AWS::EC2::Instance", "Properties": {}},
        })
        result = translate(tmpl, mode="supported")
        assert "MyBucket" in result["kept"]
        assert "MyEC2" in result["dropped"]
        assert result["stats"]["kept"] == 1
        assert result["stats"]["dropped"] == 1

    def test_security_mode_filters_stricter(self) -> None:
        tmpl = self._make_template({
            "MyRole": {"Type": "AWS::IAM::Role", "Properties": {}},
            "MyLogGroup": {"Type": "AWS::Logs::LogGroup", "Properties": {}},
        })
        result = translate(tmpl, mode="security")
        assert "MyRole" in result["kept"]
        assert "MyLogGroup" in result["dropped"]

    def test_output_is_valid_yaml(self) -> None:
        tmpl = self._make_template({
            "Tbl": {"Type": "AWS::DynamoDB::Table", "Properties": {}},
        })
        result = translate(tmpl)
        parsed = yaml.safe_load(result["template"])
        assert "Tbl" in parsed["Resources"]

    def test_empty_resources_returns_error(self) -> None:
        result = translate("AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n")
        assert "error" in result

    def test_invalid_yaml_returns_error(self) -> None:
        result = translate("{{not yaml")
        assert "error" in result

    @settings(max_examples=30)
    @given(n_supported=st.integers(min_value=0, max_value=5),
           n_unsupported=st.integers(min_value=0, max_value=5))
    def test_kept_plus_dropped_equals_total(
        self, n_supported: int, n_unsupported: int,
    ) -> None:
        if n_supported + n_unsupported == 0:
            return
        resources = {}
        for i in range(n_supported):
            resources[f"Bucket{i}"] = {
                "Type": "AWS::S3::Bucket", "Properties": {},
            }
        for i in range(n_unsupported):
            resources[f"EC2{i}"] = {
                "Type": "AWS::EC2::Instance", "Properties": {},
            }
        result = translate(self._make_template(resources))
        assert result["stats"]["kept"] + result["stats"]["dropped"] == (
            n_supported + n_unsupported
        )

    def test_vpc_props_stripped(self) -> None:
        tmpl = self._make_template({
            "Fn": {"Type": "AWS::Lambda::Function", "Properties": {
                "FunctionName": "test",
                "VpcConfig": {"SubnetIds": ["s-1"], "SecurityGroupIds": ["sg-1"]},
            }},
        })
        result = translate(tmpl)
        parsed = yaml.safe_load(result["template"])
        props = parsed["Resources"]["Fn"]["Properties"]
        assert "VpcConfig" not in props
