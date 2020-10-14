# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import socket
import logging
import xmlrpc.client
from odoo.addons.component.core import AbstractComponent
from odoo.addons.queue_job.exception import FailedJobError
from odoo.addons.connector.exception import NetworkRetryableError, RetryableJobError
from datetime import datetime

_logger = logging.getLogger(__name__)

try:
    from woocommerce import API
except ImportError:
    _logger.debug("cannot import 'woocommerce'")

recorder = {}

WOO_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


def call_to_key(method, arguments):
    """ Used to 'freeze' the method and arguments of a call to WooCommerce
    so they can be hashable; they will be stored in a dict.

    Used in both the recorder and the tests.
    """

    def freeze(arg):
        if isinstance(arg, dict):
            items = dict((key, freeze(value)) for key, value in arg.items())
            return frozenset(iter(items.items()))
        elif isinstance(arg, list):
            return tuple([freeze(item) for item in arg])
        else:
            return arg

    new_args = []
    for arg in arguments:
        new_args.append(freeze(arg))
    return (method, tuple(new_args))


def record(method, arguments, result):
    """ Utility function which can be used to record test data
    during synchronisations. Call it from WooCRUDAdapter._call

    Then ``output_recorder`` can be used to write the data recorded
    to a file.
    """
    recorder[call_to_key(method, arguments)] = result


def output_recorder(filename):
    import pprint

    with open(filename, "w") as f:
        pprint.pprint(recorder, f)
    _logger.debug("recorder written to file %s", filename)


class WooLocation(object):
    def __init__(self, location, consumer_key, consumer_secret):
        self._location = location
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    @property
    def location(self):
        location = self._location
        return location


class WooAPI(object):
    def __init__(self, location):
        """
        :param location: Woocommerce Location
        :type location: :class:`WooLocation`
        """
        self._location = location
        self._api = None

    @property
    def api(self):
        if self._api is None:
            api = API(
                url=self._location.location,
                consumer_key=self._location.consumer_key,
                consumer_secret=self._location.consumer_secret,
                wp_api=True,
                version="wc/v2",
                timeout=30
            )
            self._api = api
        return self._api

    def get(self, method, arguments):
        try:
            start = datetime.now()
            try:
                response = self.api.get(method, params=arguments)
                response_json = response.json()
                if not response.ok:
                    if response_json.get("code") and response_json.get("message"):
                        raise FailedJobError(
                            "%s error: %s - %s"
                            % (
                                response.status_code,
                                response_json["code"],
                                response_json["message"],
                            )
                        )
                    else:
                        return response.raise_for_status()
                result = response_json
            except:
                _logger.error("api.call(%s, %s) failed", method, arguments)
                raise
            else:
                _logger.debug(
                    "api.call(%s, %s) returned %s in %s seconds",
                    method,
                    arguments,
                    result,
                    (datetime.now() - start).seconds,
                )
            return result
        except (socket.gaierror, socket.error, socket.timeout) as err:
            raise NetworkRetryableError(
                "A network error caused the failure of the job: " "%s" % err
            )
        except xmlrpc.client.ProtocolError as err:
            if err.errcode in [
                502,  # Bad gateway
                503,  # Service unavailable
                504,
            ]:  # Gateway timeout
                raise RetryableJobError(
                    "A protocol error caused the failure of the job:\n"
                    "URL: %s\n"
                    "HTTP/HTTPS headers: %s\n"
                    "Error code: %d\n"
                    "Error message: %s\n"
                    % (err.url, err.headers, err.errcode, err.errmsg)
                )
            else:
                raise

    def put(self, method, arguments):
        try:
            start = datetime.now()
            try:
                response = self.api.put(method, data=arguments)
                response_json = response.json()
                if not response.ok:
                    if response_json.get("code") and response_json.get("message"):
                        raise FailedJobError(
                            "%s error: %s - %s"
                            % (
                                response.status_code,
                                response_json["code"],
                                response_json["message"],
                            )
                        )
                    else:
                        return response.raise_for_status()
                result = response_json
            except:
                _logger.error("api.call(%s, %s) failed", method, arguments)
                raise
            else:
                _logger.debug(
                    "api.call(%s, %s) returned %s in %s seconds",
                    method,
                    arguments,
                    result,
                    (datetime.now() - start).seconds,
                )
            return result
        except (socket.gaierror, socket.error, socket.timeout) as err:
            raise NetworkRetryableError(
                "A network error caused the failure of the job: " "%s" % err
            )
        except xmlrpc.client.ProtocolError as err:
            if err.errcode in [
                502,  # Bad gateway
                503,  # Service unavailable
                504,
            ]:  # Gateway timeout
                raise RetryableJobError(
                    "A protocol error caused the failure of the job:\n"
                    "URL: %s\n"
                    "HTTP/HTTPS headers: %s\n"
                    "Error code: %d\n"
                    "Error message: %s\n"
                    % (err.url, err.headers, err.errcode, err.errmsg)
                )
            else:
                raise


class WooCRUDAdapter(AbstractComponent):
    """ External Records Adapter for woo """

    _name = "woocommerce.crud.adapter"
    _inherit = ["base.backend.adapter", "base.woocommerce.connector"]
    _usage = "backend.adapter"

    def search(self, filters=None):
        """ Search records according to some criterias
        and returns a list of ids """
        raise NotImplementedError

    def read(self, external_id, attributes=None):
        """ Returns the information of a record """
        raise NotImplementedError

    def search_read(self, filters=None):
        """ Search records according to some criterias
        and returns their information"""
        raise NotImplementedError

    def create(self, data):
        """ Create a record on the external system """
        raise NotImplementedError

    def write(self, external_id, data):
        """ Update records on the external system """
        raise NotImplementedError

    def delete(self, external_id):
        """ Delete a record on the external system """
        raise NotImplementedError

    def _get(self, method, arguments):
        try:
            wc_api = getattr(self.work, "wc_api")
        except AttributeError:
            raise AttributeError(
                "You must provide a wc_api attribute with a "
                "WooAPI instance to be able to use the "
                "Backend Adapter."
            )
        return wc_api.get(method, arguments)

    def _put(self, method, arguments):
        try:
            wc_api = getattr(self.work, "wc_api")
        except AttributeError:
            raise AttributeError(
                "You must provide a wc_api attribute with a "
                "WooAPI instance to be able to use the "
                "Backend Adapter."
            )
        return wc_api.put(method, arguments)


class GenericAdapter(AbstractComponent):

    _name = "woocommerce.adapter"
    _inherit = "woocommerce.crud.adapter"

    _woo_model = None

    def search(self, filters=None, from_date=None, to_date=None):
        """ Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        if filters is None:
            filters = {}
        dt_fmt = WOO_DATETIME_FORMAT
        filters["per_page"] = 25
        if from_date:
            # updated_at include the created records
            filters["updated_at_min"] = from_date.strftime(dt_fmt)
        if to_date:
            filters["updated_at_max"] = to_date.strftime(dt_fmt)
        objects_data = self._get(self._woo_model, filters)
        objects = objects_data
        readed = len(objects)
        while objects_data:
            filters["offset"] = readed
            objects_data = self._get(self._woo_model, filters)
            readed += len(objects)
            objects = objects + objects_data
        return [x["id"] for x in objects]

    def read(self, external_id, attributes=None):
        """ Returns the information of a record

        :rtype: dict
        """
        arguments = []
        if attributes:
            # Avoid to pass Null values in attributes. Workaround for
            # is not installed, calling info() with None in attributes
            # would return a wrong result (almost empty list of
            # attributes). The right correction is to install the
            # compatibility patch on WooCommerce.
            arguments.append(attributes)
        return self._get("{}/{}".format(self._woo_model, str(external_id)), [])

    def write(self, external_id, data):
        """ Update records on the external system """
        return self._put("{}/{}".format(self._woo_model, str(external_id)), data)
