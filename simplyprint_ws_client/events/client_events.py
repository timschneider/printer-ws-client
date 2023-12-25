from abc import abstractmethod
from enum import Enum
from typing import Any, Dict, Generator, Optional, Tuple, TYPE_CHECKING, Union

from ..helpers.intervals import IntervalException, IntervalTypes
from ..events.event import Event

if TYPE_CHECKING:
    from ..state.printer import PrinterState

class PrinterEvent(Enum):
    PING = "ping"
    KEEPALIVE = "keepalive"
    LATENCY = "latency"
    TOOL = "tool"
    STATUS = "state_change"
    AMBIENT = "ambient"
    TEMPERATURES = "temps"
    SHUTDOWN = "shutdown"
    CONNECTION = "connection"
    CAMERA_SETTINGS = "camera_settings"
    JOB_INFO = "job_info"
    FILE_PROGRESS = "file_progress"
    PSU_CHANGE = "psu_change"
    CPU_INFO = "cpu_info"
    PSU = "power_controller"
    STREAM = "stream"
    PRINTER_ERROR = "printer_error"
    MESH_DATA = "mesh_data"
    INFO = "machine_data"
    INPUT_REQUIRED = "input_required"
    UPDATE_STARTED = "update_started"
    FIRMWARE = "firmware"
    WEBCAM = "webcam"
    WEBCAM_STATUS = "webcam_status"
    UNSAFE_FIRMWARE = "unsafe_firmware"
    FILAMENT_ANALYSIS = "filament_analysis"
    OCTOPRINT_PLUGINS = "octoprint_plugins"
    GCODE_SCRIPTS = "gcode_scripts"
    INSTALLED_PLUGINS = "installed_plugins"
    SOFTWARE_UPDATES = "software_updates"
    FIRMWARE_WARNING = "firmware_warning"
    AI_RESP = "ai_resp"
    LOGS_SENT = "logs_sent"
    FILAMENT_SENSOR = "filament_sensor"
    MATERIAL_DATA = "material_data"

ALLOWED_IN_SETUP = [
    PrinterEvent.PING,
    PrinterEvent.KEEPALIVE,
    PrinterEvent.CONNECTION,
    PrinterEvent.STATUS,
    PrinterEvent.SHUTDOWN,
    PrinterEvent.INFO,
    PrinterEvent.FIRMWARE,
    PrinterEvent.FIRMWARE_WARNING,
    PrinterEvent.INSTALLED_PLUGINS,
]

class ClientEventMode(Enum):
    DISPATCH = 0
    RATELIMIT = 1
    CANCEL = 2

class ClientEvent(Event):
    event_type: PrinterEvent
    interval_type: Optional[IntervalTypes] = None
    
    state: 'PrinterState'
    for_client: Optional[Union[str, int]]
    data: Optional[Dict[str, Any]]

    def __init__(self, state = None, for_client: Optional[Union[str, int]] = None, data: Optional[Dict[str, Any]] = None) -> None:
        """
        state (PrinterState): The state of the printer at the time of the event.
        for_client (int): Id of client event belongs to
        data (Optional[Dict[str, Any]], optional): Custom data to send with the event. Defaults to None.
        """
        self.state = state
        self.for_client = for_client
        self.data = data

    @classmethod
    def get_name(cls) -> Optional[str]:
        if cls is ClientEvent:
            return None

        return cls.event_type.value

    @abstractmethod
    def generate_data(self) -> Optional[Generator[Tuple, None, None]]:
        pass

    def generate(self) -> Generator[Tuple, None, None]:
        yield "type", self.get_name()

        if not self.for_client is None and self.for_client != 0:
            yield "for", self.for_client

        if self.data is not None:
            yield "data", self.data
        elif (data_generator := self.generate_data()) is not None:
            yield "data", dict(data_generator)

    def as_dict(self) -> Dict[str, Any]:
        return dict(self.generate())
    
    def on_send(self) -> ClientEventMode:
        if self.interval_type is not None:
            try:
                self.state.intervals.use(self.interval_type.value)
            except IntervalException:
                return ClientEventMode.RATELIMIT    
    
        return ClientEventMode.DISPATCH

class GcodeScriptsEvent(ClientEvent):
    event_type = PrinterEvent.GCODE_SCRIPTS

class MachineDataEvent(ClientEvent):
    event_type = PrinterEvent.INFO
    
    def generate_data(self) -> Generator[Tuple, None, None]:
        for key, value in self.state.info.trait_values().items():
            yield key, value
    
class WebcamStatusEvent(ClientEvent):
    event_type = PrinterEvent.WEBCAM_STATUS

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "connected", self.state.webcam_info.connected

class WebcamEvent(ClientEvent):
    event_type = PrinterEvent.WEBCAM

    def generate_data(self) -> Generator[Tuple, None, None]:
        for key, value in self.state.webcam_settings.trait_values().items():
            if self.state.has_changed(self.state.webcam_settings, key):
                yield key, value

class InstalledPluginsEvent(ClientEvent):
    event_type = PrinterEvent.INSTALLED_PLUGINS

class SoftwareUpdatesEvent(ClientEvent):
    event_type = PrinterEvent.SOFTWARE_UPDATES

class FirmwareEvent(ClientEvent):
    event_type = PrinterEvent.FIRMWARE

    def generate_data(self) -> Generator[Tuple, None, None]:
        for key, value in self.state.firmware.trait_values().items():
            if self.state.has_changed(self.state.firmware, key):
                yield f"firmware_{key}", value

class FirmwareWarningEvent(ClientEvent):
    event_type = PrinterEvent.FIRMWARE_WARNING

    def generate_data(self) -> Generator[Tuple, None, None]:
        for key, value in self.state.firmware.trait_values().items():
            yield key, value

class ToolEvent(ClientEvent):
    event_type = PrinterEvent.TOOL

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "new", self.state.active_tool

class TemperatureEvent(ClientEvent):
    event_type = PrinterEvent.TEMPERATURES
    interval_type = IntervalTypes.TEMPS

    def generate_data(self) -> Generator[Tuple, None, None]:
        if self.state.has_changed(self.state.bed_temperature):
            yield "bed", self.state.bed_temperature.to_list()

        for i, tool in enumerate(self.state.tool_temperatures):
            if self.state.has_changed(tool):
                yield f"tool{i}", tool.to_list()

    def on_send(self) -> ClientEventMode:
        # If we have a target temperature, send it more often (use IntervalTypes.TEMPS_TARGET)
        if self.state.bed_temperature.target is not None or any([tool.target is not None for tool in self.state.tool_temperatures]):
            self.interval_type = IntervalTypes.TEMPS_TARGET
        else:
            self.interval_type = IntervalTypes.TEMPS

        return super().on_send()

class AmbientTemperatureEvent(ClientEvent):
    event_type = PrinterEvent.AMBIENT

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "new", round(self.state.ambient_temperature.ambient)

class ConnectionEvent(ClientEvent):
    event_type = PrinterEvent.CONNECTION

class StateChangeEvent(ClientEvent):
    event_type = PrinterEvent.STATUS

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "new", self.state.status.value

class JobInfoEvent(ClientEvent):
    event_type = PrinterEvent.JOB_INFO
    interval_type = IntervalTypes.JOB
    force_dispatch: bool = False

    def generate_data(self) -> Generator[Tuple, None, None]:
        for key, value in self.state.job_info.trait_values().items():
            if self.state.has_changed(self.state.job_info, key):
                if key in ["started", "finished", "cancelled", "failed"]:
                    # Only send updates in terms of true, since they
                    # are mutually exclusive.
                    if not value: continue
        
                yield key, value if key != 'progress' else round(value)
    
    def on_send(self) -> ClientEventMode:
        # Ensure we never drop job status updates
        return ClientEventMode.DISPATCH

# TODO in the future
class AiResponseEvent(ClientEvent):
    event_type = PrinterEvent.AI_RESP

class PrinterErrorEvent(ClientEvent):
    event_type = PrinterEvent.PRINTER_ERROR

class ShutdownEvent(ClientEvent):
    event_type = PrinterEvent.SHUTDOWN

class StreamEvent(ClientEvent):
    event_type = PrinterEvent.STREAM
    interval_type = IntervalTypes.WEBCAM

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "base", self.data.get("base")

class PingEvent(ClientEvent):
    event_type = PrinterEvent.PING
    interval_type = IntervalTypes.PING

    def generate_data(self) -> Generator[Tuple, None, None]:
        ...

class LatencyEvent(ClientEvent):
    event_type = PrinterEvent.LATENCY

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "ms", self.state.latency.pong - self.state.latency.ping

class FileProgressEvent(ClientEvent):
    event_type = PrinterEvent.FILE_PROGRESS

    def generate_data(self) -> Generator[Tuple, None, None]:
        """
        When a file progress event is triggered, always yield state, the two other fields 
        percent and message are optionally tied to respectfully downloading and error states.

        But since we always send the state you can update any other fields you want to send and still 
        achieve the same result.
        """
        yield "state", self.state.file_progress.state.value

        if self.state.file_progress.state.value == "error":
            yield "message", self.state.file_progress.message or "Unknown error"

        for key, value in self.state.file_progress.trait_values().items():
            if key in ["state", "message"]: continue

            if self.state.has_changed(self.state.file_progress, key):
                yield key, value

    def on_send(self) -> ClientEventMode:
        # Ensure we never drop file progress updates
        return ClientEventMode.DISPATCH


class FilamentSensorEvent(ClientEvent):
    event_type = PrinterEvent.FILAMENT_SENSOR

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "state", self.state.filament_sensor.state

class PowerControllerEvent(ClientEvent):
    event_type = PrinterEvent.PSU

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "on", self.state.psu_info.on

class CpuInfoEvent(ClientEvent):
    event_type = PrinterEvent.CPU_INFO
    interval_type = IntervalTypes.CPU

    def generate_data(self) -> Generator[Tuple, None, None]:
        for key, value in vars(self.state.cpu_info).get("_trait_values", dict()).items():
            if self.state.has_changed(self.state.cpu_info, key):
                yield key, value

class MeshDataEvent(ClientEvent):
    event_type = PrinterEvent.MESH_DATA

class LogsSentEvent(ClientEvent):
    event_type = PrinterEvent.LOGS_SENT

class MaterialDataEvent(ClientEvent):
    event_type = PrinterEvent.MATERIAL_DATA
    has_changes = False

    def generate_data(self) -> Generator[Tuple, None, None]:
        if self.state.has_changed(self.state, "material_data"):
            if len(self.state.material_data) == 0: return
            yield "materials", [material.trait_values() for material in self.state.material_data]
            self.has_changes = True

    def on_send(self) -> ClientEventMode:
        if self.has_changes:
            return ClientEventMode.DISPATCH
        
        return ClientEventMode.CANCEL