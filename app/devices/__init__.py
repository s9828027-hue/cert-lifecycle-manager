from app.devices import f5_client, ise_client

_CLIENTS = {"F5": f5_client, "ISE": ise_client}


def get_client(device_type: str):
    try:
        return _CLIENTS[device_type.upper()]
    except KeyError:
        raise ValueError(f"未支援的設備類型: {device_type}（目前支援 F5、ISE）")
