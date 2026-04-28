"""Persistence for feature vectors keyed by log id + anomaly type."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.models.code_service.log_feature_engineering import (
    LogFeatureEngineering as TableModel,
)
from app.models.code_service.prediction_result import (
    PredictionResult as PredictionResultModel,
)
from app.schemas.code_service.log_feature_engineering import (
    BatchLookupRequest,
    LogKind,
    StoredFeatureRecord,
    UpsertRequest,
)

logger = logging.getLogger(__name__)


class LogFeatureEngineeringRepository:
    """Read/upsert ``core.logfeatureengineering`` and prediction rows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_record(self, row: TableModel) -> StoredFeatureRecord:
        return StoredFeatureRecord(
            id=row.id,
            visitor_log_id=row.visitor_log_id,
            resident_log_id=row.resident_log_id,
            anomaly_type=row.anomaly_type,
            log_kind=row.log_kind,
            features_visitor_specific=row.features_visitor_specific,
            features_resident_specific=row.features_resident_specific,
            features_security_specific=row.features_security_specific,
            features_estate_wide=row.features_estate_wide,
            is_anomalous=bool(row.is_anomalous),
        )

    async def batch_lookup(
        self, request: BatchLookupRequest
    ) -> list[StoredFeatureRecord]:
        """Return rows for ``log_ids`` in the table from ``log_kind``."""
        if not request.log_ids:
            return []
        ids = [UUID(str(x)) for x in request.log_ids]
        if request.log_kind == LogKind.VISITOR:
            col = TableModel.visitor_log_id
        else:
            col = TableModel.resident_log_id
        try:
            q = select(TableModel).where(
                TableModel.is_deleted == False,  # noqa: E712
                TableModel.is_anomalous == False,  # noqa: E712
                TableModel.anomaly_type == request.anomaly_type,
                TableModel.log_kind == request.log_kind,
                col.in_(ids),
            )
            result = await self.session.execute(q)
            rows = result.scalars().all()
            return [self._to_record(r) for r in rows]
        except SQLAlchemyError as e:
            logger.exception("batch_lookup log feature engineering")
            raise DatabaseError("Database error in batch_lookup") from e

    async def upsert(self, request: UpsertRequest) -> UUID:
        """
        Insert or update the single active row for (log id, anomaly_type).

        Feature JSON columns are updated only when the request field is not
        ``None``. If ``prediction_type`` + ``prediction_result`` are supplied,
        upsert one ``core.predictionresult`` row for the same feature-log id.
        """
        try:
            if request.visitor_log_id is not None:
                q = select(TableModel).where(
                    TableModel.is_deleted == False,  # noqa: E712
                    TableModel.visitor_log_id == request.visitor_log_id,
                    TableModel.anomaly_type == request.anomaly_type,
                )
            else:
                q = select(TableModel).where(
                    TableModel.is_deleted == False,  # noqa: E712
                    TableModel.resident_log_id == request.resident_log_id,
                    TableModel.anomaly_type == request.anomaly_type,
                )
            result = await self.session.execute(q)
            row = result.scalar_one_or_none()
            if row is None:
                row = TableModel(
                    visitor_log_id=request.visitor_log_id,
                    resident_log_id=request.resident_log_id,
                    anomaly_type=request.anomaly_type,
                    log_kind=request.log_kind,
                    features_visitor_specific=(
                        request.features_visitor_specific
                    ),
                    features_resident_specific=(
                        request.features_resident_specific
                    ),
                    features_security_specific=(
                        request.features_security_specific
                    ),
                    features_estate_wide=request.features_estate_wide,
                    is_anomalous=(
                        request.is_anomalous
                        if request.is_anomalous is not None
                        else False
                    ),
                )
                self.session.add(row)
            else:
                row.anomaly_type = request.anomaly_type
                row.log_kind = request.log_kind
                if request.features_visitor_specific is not None:
                    row.features_visitor_specific = (
                        request.features_visitor_specific
                    )
                if request.features_resident_specific is not None:
                    row.features_resident_specific = (
                        request.features_resident_specific
                    )
                if request.features_security_specific is not None:
                    row.features_security_specific = (
                        request.features_security_specific
                    )
                if request.features_estate_wide is not None:
                    row.features_estate_wide = request.features_estate_wide
                if request.is_anomalous is not None:
                    row.is_anomalous = request.is_anomalous
            await self.session.flush()
            await self.session.refresh(row)
            if (
                request.prediction_type is not None
                and request.prediction_result is not None
            ):
                prediction_q = select(PredictionResultModel).where(
                    PredictionResultModel.is_deleted == False,  # noqa: E712
                    PredictionResultModel.feature_log_id == row.id,
                    PredictionResultModel.prediction_type
                    == request.prediction_type,
                )
                prediction_result = (
                    await self.session.execute(prediction_q)
                ).scalar_one_or_none()
                if prediction_result is None:
                    prediction_result = PredictionResultModel(
                        feature_log_id=row.id,
                        visitor_log_id=request.visitor_log_id,
                        resident_log_id=request.resident_log_id,
                        prediction_type=request.prediction_type,
                        result=request.prediction_result,
                    )
                    self.session.add(prediction_result)
                else:
                    prediction_result.visitor_log_id = request.visitor_log_id
                    prediction_result.resident_log_id = request.resident_log_id
                    prediction_result.result = request.prediction_result
            return row.id
        except SQLAlchemyError as e:
            logger.exception("upsert log feature engineering")
            raise DatabaseError("Database error in upsert") from e
