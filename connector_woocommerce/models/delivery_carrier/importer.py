# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from odoo.addons.connector.components.mapper import mapping, only_create
from odoo.addons.component.core import Component

_logger = logging.getLogger(__name__)


class DeliveryCarrierBatchImporter(Component):
    """
        Import the WooCommerce carriers.
    """

    _name = "woocommerce.delivery.carrier.batch.importer"
    _inherit = "woocommerce.delayed.batch.importer"
    _apply_on = ["woo.delivery.carrier"]

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop("from_date", None)
        to_date = filters.pop("to_date", None)
        record_ids = self.backend_adapter.search(
            filters, from_date=from_date, to_date=to_date
        )
        _logger.debug("search for woo carriers %s returned %s", filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)


class DeliveryCarrierImportMapper(Component):
    _name = "woocommerce.delivery.carrier.import.mapper"
    _inherit = "woocommerce.import.mapper"
    _apply_on = "woo.delivery.carrier"

    direct = [("title", "name"), ("id", "woocommerce_id")]

    @only_create
    @mapping
    def product_id(self, record):
        return {"product_id": self.backend_record.shipping_product_id.id}

    @mapping
    def backend_id(self, record):
        return {"backend_id": self.backend_record.id}


class DeliveryCarrierImporter(Component):
    _name = "woocommerce.delivery.carrier.importer"
    _inherit = "woocommerce.importer"
    _apply_on = ["woo.delivery.carrier"]
