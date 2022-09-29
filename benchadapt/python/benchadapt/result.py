import datetime
import uuid
import warnings
from dataclasses import asdict, dataclass, field
from typing import Any, Dict

from .machine_info import github_info, machine_info


@dataclass
class BenchmarkResult:
    """
    A dataclass for containing results from running a benchmark.

    Attributes
    ----------
    run_name : str
        Name for the run. Current convention is ``f"{run_reason}: {github['commit']}"``.
        If missing and ``github["commmit"]`` exists, ``run_name`` will be populated
        according to that pattern (even if ``run_reason`` is ``None``); otherwise it will
        remain ``None``. Users should not set this manually unless they want to identify
        runs in some other fashion. Benchmark name should be specified in ``tags["name"]``.
    run_id : str
        ID for the run; should be consistent for all results of the run. Should not normally
        be set manually; adapters will handle this for you.
    batch_id : str
        ID string for the batch
    run_reason : str
        Reason for run (e.g. commit, PR, merge, nightly). In many cases will be set at
        runtime via an adapter's ``result_fields_override`` init parameter; should not
        usually be set in ``_transform_results()``.
    timestamp : str
        Timestamp of call, in ISO format
    stats : Dict[str, Any]
        Measurement data and summary statistics. If ``data`` (a list of metric values),
        ``unit`` (for that metric, e.g. ``"s"``), and ``iterations`` (replications for
        microbenchmarks) are specified, summary statistics will be filled in server-side.
    tags : Dict[str, Any]
        Many things. Must include a ``name`` element (i.e. the benchmark name); often
        includes parameters either as separate keys or as a string in a ``params`` key.
        If suite subdivisions exist, use a ``suite`` tag. Determines history runs.
    info : Dict[str, Any]
        Things like ``arrow_version``, ``arrow_compiler_id``, ``arrow_compiler_version``,
        ``benchmark_language_version, ``arrow_version_r``
    machine_info : Dict[str, Any]
        For benchmarks run on a single node, information about the machine, e.g. OS,
        architecture, etc. Auto-populated if ``cluster_info`` not set.
    cluster_info : Dict[str, Any]
        For benchmarks run on a cluster, information about the cluster
    context : Dict[str, Any]
        Should include ``benchmark_language`` and other relevant metadata like compiler flags
    github : Dict[str, Any]
        Keys: ``repository``, ``commit``. If unspecified, will be auto-populated based on
        the current git state.
    error : str
        stderr from process running the benchmark

    Fields one of which must be supplied, the other of which will not be posted to conbench:

    - ``machine_info`` (generated by default) or ``cluster_info``
    - ``stats`` or ``error``

    Fields which should generally not be specified directly on instantiation that will
    be set later for the run:

    - ``run_name``
    - ``run_id``
    - ``run_reason``

    Fields without comprehensive defaults which should be specified directly:

    - ``stats`` (or ``error``)
    - ``tags``
    - ``info``
    - ``context``

    Fields with defaults you may want to override on instantiation:

    - ``batch_id`` if multiple benchmarks should be grouped, e.g. for a suite
    - ``timestamp`` if run time is inaccurate
    - ``machine_info`` if not run on the current machine
    - ``cluster_info`` if run on a cluster
    - ``github`` if current git info is unavailable or inaccurate
    """

    run_name: str = None
    run_id: str = None
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    run_reason: str = None
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    stats: Dict[str, Any] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    info: Dict[str, Any] = field(default_factory=dict)
    machine_info: Dict[str, Any] = field(
        default_factory=lambda: machine_info(host_name=None)
    )
    cluster_info: Dict[str, Any] = None
    context: Dict[str, Any] = field(default_factory=dict)
    github: Dict[str, Any] = field(default_factory=github_info)
    error: str = None

    def __post_init__(self) -> None:
        if not self.run_name and self.github.get("commit"):
            self.run_name = f"{self.run_reason}: {self.github['commit']}"

    @property
    def _cluster_info_property(self) -> Dict[str, Any]:
        return self._cluster_info_cache

    @_cluster_info_property.setter
    def _cluster_info_property(self, value: Dict[str, Any]) -> None:
        if value:
            self.machine_info = None
        self._cluster_info_cache = value

    def to_publishable_dict(self):
        """Returns a dict suitable for sending to conbench"""
        res_dict = asdict(self)

        if bool(res_dict.get("machine_info")) != bool(not res_dict["cluster_info"]):
            warnings.warn(
                "Result not publishable! `machine_info` xor `cluster_info` must be specified"
            )

        if bool(res_dict["stats"]) == bool(res_dict["error"]):
            warnings.warn(
                "Result not publishable! `stats` xor `error` must be be specified"
            )

        for attr in ["machine_info", "cluster_info", "stats", "error"]:
            if not res_dict[attr]:
                res_dict.pop(attr)

        return res_dict


# Ugly, but per https://stackoverflow.com/a/61480946 lets us keep defaults and order
BenchmarkResult.cluster_info = BenchmarkResult._cluster_info_property