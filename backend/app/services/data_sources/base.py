"""
VoltAI Data Source Abstraction Layer

Architectural Principle:
    All energy data entering VoltAI must pass through a DataSource adapter that
    normalizes raw vendor/format-specific inputs (CSV, Smart Meter, IoT, SCADA,
    Weather/Grid APIs) into standard EnergyReadingCreate schemas.

    Downstream business logic (analytics, forecasting, anomaly detection,
    optimization) NEVER couples directly to physical input mechanisms like CSV files.
"""

from abc import ABC, abstractmethod
from typing import Iterator, List

from backend.app.schemas.energy import EnergyReadingCreate


class BaseDataSource(ABC):
    """
    Abstract Base Class for all VoltAI telemetry data sources.

    Subclasses implement format-specific extraction and normalization
    (e.g., CSVDataSource, SmartMeterDataSource, IoTDataSource, SCADADataSource).
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """
        Identifier for the source type (e.g., 'csv', 'smart_meter', 'iot', 'scada').
        """
        pass

    @abstractmethod
    def read_readings(self) -> Iterator[EnergyReadingCreate]:
        """
        Stream or iterate over normalized energy readings produced by this data source.

        Yields:
            EnergyReadingCreate: Validated normalized reading.
        """
        pass

    def fetch_all(self) -> List[EnergyReadingCreate]:
        """
        Convenience method to collect all normalized readings into a list.

        Returns:
            List[EnergyReadingCreate]: In-memory list of validated readings.
        """
        return list(self.read_readings())
