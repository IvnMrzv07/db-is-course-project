"""Which MongoDB failures mean "the cluster cannot do this now" (retry without limit) rather than "the data is bad"."""
from pymongo.errors import BulkWriteError, ConnectionFailure, OperationFailure, PyMongoError

# Server codes seen while a shard, its primary or the router is absent or changing.
TRANSIENT_CODES = frozenset({
    6, 7, 89, 9001,            # HostUnreachable, HostNotFound, NetworkTimeout, SocketException
    91, 11600, 11602,          # ShutdownInProgress, InterruptedAtShutdown, InterruptedDueToReplStateChange
    133,                       # FailedToSatisfyReadPreference: mongos finds no primary for a shard
    189, 10107, 13435, 13436,  # PrimarySteppedDown, NotWritablePrimary, NotPrimaryNoSecondaryOk, NotPrimaryOrSecondary
    50, 202, 262,              # MaxTimeMSExpired, NetworkInterfaceExceededTimeLimit, ExceededTimeLimit
    64,                        # WriteConcernTimeout
    112, 246, 251, 290,        # WriteConflict, SnapshotUnavailable, NoSuchTransaction, TransactionExceededLifetimeLimit
    63, 150, 13388,            # StaleShardVersion, StaleEpoch, StaleConfig: the router refreshes routing
})
_LABELS = ('TransientTransactionError', 'UnknownTransactionCommitResult', 'RetryableWriteError')


def is_unavailable(error: BaseException) -> bool:
    if not isinstance(error, PyMongoError):
        return False
    if isinstance(error, ConnectionFailure) or error.timeout or any(error.has_error_label(label) for label in _LABELS):
        return True
    if isinstance(error, BulkWriteError):
        details = error.details or {}
        codes = [entry.get('code') for entry in (*details.get('writeErrors', ()), *details.get('writeConcernErrors', ()))]
        return bool(codes) and all(code in TRANSIENT_CODES for code in codes)
    return isinstance(error, OperationFailure) and error.code in TRANSIENT_CODES
