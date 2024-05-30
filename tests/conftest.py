import dataclasses
import pathlib

import pytest

from example_device import ExampleDevice
from shv import RpcLogin, RpcLoginType, RpcUrl, SimpleClient, ValueClient, broker


@pytest.fixture(name="port", scope="module")
def fixture_port(unused_tcp_port_factory):
    """Override for port for shvbroker."""
    return unused_tcp_port_factory()


@pytest.fixture(name="sslport", scope="module")
def fixture_sslport(unused_tcp_port_factory):
    """Override for sslPort for shvbroker."""
    return unused_tcp_port_factory()


@pytest.fixture(name="url", scope="module")
def fixture_url(port):
    """Provide RpcUrl for connecting to the broker."""
    return RpcUrl(
        location="localhost",
        port=port,
        login=RpcLogin(
            username="admin",
            password="admin!123",
            login_type=RpcLoginType.PLAIN,
        ),
    )


@pytest.fixture(name="url_test", scope="module")
def fixture_url_test(url):
    return dataclasses.replace(
        url, login=dataclasses.replace(url.login, username="test", password="test")
    )


@pytest.fixture(name="url_test_device", scope="module")
def fixture_url_test_device(url_test):
    return dataclasses.replace(
        url_test,
        login=dataclasses.replace(
            url_test.login, options={"device": {"mountPoint": "test/device"}}
        ),
    )


@pytest.fixture(name="shvbroker_config", scope="module")
def fixture_shvbroker_config(port):
    conf = broker.RpcBrokerConfig.load(
        pathlib.Path(__file__).parent / "broker" / "config.toml"
    )
    conf.listen["internet"].port = port
    del conf.listen["unix"]
    return conf


@pytest.fixture(name="shvbroker")
async def fixture_shvbroker(port, shvbroker_config):
    """SHV broker usable for all tests."""
    b = broker.RpcBroker(shvbroker_config)
    await b.start_serving()
    yield b
    await b.terminate()


@pytest.fixture(name="client")
async def fixture_client(shvbroker, url):
    client = await SimpleClient.connect(url)
    yield client
    await client.disconnect()


@pytest.fixture(name="value_client")
async def fixture_value_client(shvbroker, url_test):
    client = await ValueClient.connect(url_test)
    yield client
    await client.disconnect()


@pytest.fixture(name="example_device")
async def fixture_example_device(shvbroker, url_test_device):
    """Run example device and provide instance to access it."""
    device = await ExampleDevice.connect(url_test_device)
    yield device
    await device.disconnect()
