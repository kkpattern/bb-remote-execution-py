# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from remoteworker import remoteworker_pb2 as remoteworker_dot_remoteworker__pb2


class OperationQueueStub(object):
    """Buildbarn's workers connect to the scheduler to receive instructions
    on what they should be doing. They can either be instructed to be
    idle or to execute a build action. They can also report their state
    to the scheduler. The purpose of reporting state is twofold:

    - Upon completion of a build action, the worker reports the outcome
    of the build action, so that it may be communicated back to a
    client.
    - It allows for centralized management/insight in the functioning of
    the build cluster.

    All of this exchange of information takes place through a single type
    of RPC named Synchronize(), called by the worker against the
    scheduler. The worker provides information about its identity and its
    current state. The scheduler responds with instructions on whether to
    do something different or to continue.

    Every response contains a timestamp that instructs the worker when to
    resynchronize. Calls to Synchronize() are guaranteed to be
    non-blocking when it is executing a build action. They may be
    blocking in case the worker is idle or reporting the completion of a
    build action.  In that case the scheduler may decide to let the call
    hang until more work is available.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Synchronize = channel.unary_unary(
                '/buildbarn.remoteworker.OperationQueue/Synchronize',
                request_serializer=remoteworker_dot_remoteworker__pb2.SynchronizeRequest.SerializeToString,
                response_deserializer=remoteworker_dot_remoteworker__pb2.SynchronizeResponse.FromString,
                )


class OperationQueueServicer(object):
    """Buildbarn's workers connect to the scheduler to receive instructions
    on what they should be doing. They can either be instructed to be
    idle or to execute a build action. They can also report their state
    to the scheduler. The purpose of reporting state is twofold:

    - Upon completion of a build action, the worker reports the outcome
    of the build action, so that it may be communicated back to a
    client.
    - It allows for centralized management/insight in the functioning of
    the build cluster.

    All of this exchange of information takes place through a single type
    of RPC named Synchronize(), called by the worker against the
    scheduler. The worker provides information about its identity and its
    current state. The scheduler responds with instructions on whether to
    do something different or to continue.

    Every response contains a timestamp that instructs the worker when to
    resynchronize. Calls to Synchronize() are guaranteed to be
    non-blocking when it is executing a build action. They may be
    blocking in case the worker is idle or reporting the completion of a
    build action.  In that case the scheduler may decide to let the call
    hang until more work is available.
    """

    def Synchronize(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_OperationQueueServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Synchronize': grpc.unary_unary_rpc_method_handler(
                    servicer.Synchronize,
                    request_deserializer=remoteworker_dot_remoteworker__pb2.SynchronizeRequest.FromString,
                    response_serializer=remoteworker_dot_remoteworker__pb2.SynchronizeResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'buildbarn.remoteworker.OperationQueue', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class OperationQueue(object):
    """Buildbarn's workers connect to the scheduler to receive instructions
    on what they should be doing. They can either be instructed to be
    idle or to execute a build action. They can also report their state
    to the scheduler. The purpose of reporting state is twofold:

    - Upon completion of a build action, the worker reports the outcome
    of the build action, so that it may be communicated back to a
    client.
    - It allows for centralized management/insight in the functioning of
    the build cluster.

    All of this exchange of information takes place through a single type
    of RPC named Synchronize(), called by the worker against the
    scheduler. The worker provides information about its identity and its
    current state. The scheduler responds with instructions on whether to
    do something different or to continue.

    Every response contains a timestamp that instructs the worker when to
    resynchronize. Calls to Synchronize() are guaranteed to be
    non-blocking when it is executing a build action. They may be
    blocking in case the worker is idle or reporting the completion of a
    build action.  In that case the scheduler may decide to let the call
    hang until more work is available.
    """

    @staticmethod
    def Synchronize(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/buildbarn.remoteworker.OperationQueue/Synchronize',
            remoteworker_dot_remoteworker__pb2.SynchronizeRequest.SerializeToString,
            remoteworker_dot_remoteworker__pb2.SynchronizeResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
