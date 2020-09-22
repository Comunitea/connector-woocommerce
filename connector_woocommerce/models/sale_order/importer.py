# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging
from odoo import _
from datetime import datetime, timedelta
from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping
from odoo.addons.queue_job.exception import FailedJobError, NothingToDoJob
from odoo.addons.connector_woocommerce.components.backend_adapter import (
    WOO_DATETIME_FORMAT,
)

_logger = logging.getLogger(__name__)


class SaleOrderBatchImporter(Component):
    """ Import the WooCommerce Orders.

    For every order in the list, a delayed job is created.
    """

    _name = "woocommerce.sale.order.batch.importer"
    _inherit = "woocommerce.delayed.batch.importer"
    _apply_on = ["woo.sale.order"]

    def _import_record(self, external_id, job_options=None, **kwargs):
        job_options = {"max_retries": 0, "priority": 5}
        return super(SaleOrderBatchImporter, self)._import_record(
            external_id, job_options=job_options
        )

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop("from_date", None)
        to_date = filters.pop("to_date", None)
        record_ids = self.backend_adapter.search(
            filters, from_date=from_date, to_date=to_date
        )
        order_ids = []
        for record_id in record_ids:
            woo_sale_order = self.env["woo.sale.order"].search(
                [("external_id", "=", record_id)]
            )
            if woo_sale_order:
                continue
                self.update_existing_order(woo_sale_order[0], record_id)
            else:
                order_ids.append(record_id)
        _logger.info("search for woo partners %s returned %s", filters, record_ids)
        for record_id in order_ids:
            self._import_record(record_id)


class SaleImportRule(Component):
    _name = "woo.sale.import.rule"
    _inherit = "base.woocommerce.connector"
    _apply_on = "woo.sale.order"
    _usage = "sale.import.rule"

    def check(self, record):
        """ Check whether the current sale order should be imported
        or not. It will actually use the payment mode configuration
        and see if the chosen rule is fullfilled.

        :returns: True if the sale order should be imported
        :rtype: boolean
        """
        woo_payment_method = record["payment_method"]
        woo_payment_method_name = record["payment_method_title"]
        mode_binder = self.binder_for("account.payment.mode")
        payment_mode = mode_binder.to_internal(woo_payment_method)
        if not payment_mode:
            raise FailedJobError(
                _(
                    "The configuration is missing for the Payment Mode '%s'.\n\n"
                    "Resolution:\n"
                    "- Go to 'Invoicing > Configuration > Management "
                    "> Payment Modes'\n"
                    "- Create a new Payment Mode with Woocommerce code '%s'\n"
                    "-Eventually  link the Payment Method to an existing Workflow "
                    "Process or create a new one."
                )
                % (woo_payment_method_name, woo_payment_method)
            )
        self._rule_global(record, payment_mode)
        self._rule_state(record, payment_mode)

    def _rule_global(self, record, mode):
        """ Rule always executed, whichever is the selected rule """
        order_id = record["id"]
        max_days = mode.days_before_cancel
        if not max_days:
            return
        order_date = datetime.strptime(record["date_created"], WOO_DATETIME_FORMAT)
        if order_date + timedelta(days=max_days) < datetime.now():
            raise NothingToDoJob(
                "Import of the order %s canceled "
                "because it has not been paid since %d "
                "days" % (order_id, max_days)
            )

    def _rule_state(self, record, mode):
        """Check if order is importable by its state.

        If `backend_record.importable_order_state_ids` is valued
        we check if current order is in the list.
        If not, the job fails gracefully.
        """
        if self.backend_record.importable_order_state_ids:
            woo_state_name = record["status"]

            state = self.env["woo.sale.order.status"].search(
                [("name", "=", woo_state_name)], limit=1
            )
            if not state:
                raise FailedJobError(
                    _(
                        "The configuration is missing "
                        "for sale order state with PS ID=%s.\n\n"
                        "Resolution:\n"
                        " - Use the automatic import in 'Connectors > Woocommerce "
                        "Backends', button 'Synchronize base data'."
                    )
                    % (woo_state_name,)
                )
            if state not in self.backend_record.importable_order_state_ids:
                raise NothingToDoJob(
                    _(
                        "Import of the order with PS ID=%s canceled "
                        "because its state is not importable"
                    )
                    % record["id"]
                )


class SaleOrderImporter(Component):
    _name = "woocommerce.sale.order.importer"
    _inherit = "woocommerce.importer"
    _apply_on = ["woo.sale.order"]

    def _import_addresses(self):
        record = self.woo_record
        self._import_dependency(record["customer_id"], "woo.res.partner", always=True)

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        record = self.woo_record

        self._import_addresses()
        record = record["items"]
        for line in record:
            _logger.debug("line: %s", line)
            if "product_id" in line:
                self._import_dependency(line["product_id"], "woo.product.template", always=True)

    def _must_skip(self):
        """ Return True if the import can be skipped """
        if self._get_binding():
            return True
        rules = self.component(usage="sale.import.rule")
        try:
            return rules.check(self.woo_record)
        except NothingToDoJob as err:
            # we don't let the NothingToDoJob exception let go out, because if
            # we are in a cascaded import, it would stop the whole
            # synchronization and set the whole job to done
            return str(err)

    def _clean_woo_items(self, resource):
        """
        Method that clean the sale order line given by WooCommerce before
        importing it

        This method has to stay here because it allow to customize the
        behavior of the sale order.

        """
        child_items = {}  # key is the parent item id
        top_items = []

        # Group the childs with their parent
        for item in resource["line_items"]:
            if item.get("parent_item_id"):
                child_items.setdefault(item["parent_item_id"], []).append(item)
            else:
                top_items.append(item)

        all_items = []
        for top_item in top_items:
            all_items.append(top_item)
        resource["items"] = all_items
        return resource

    def _get_woo_data(self):
        """ Return the raw WooCommerce data for ``self.external_id`` """
        record = super(SaleOrderImporter, self)._get_woo_data()
        # sometimes we need to clean woo items (ex : configurable
        # product in a sale)
        record = self._clean_woo_items(record)
        return record

    def _add_shipping_line(self, binding):
        shipping_total = binding.total_shipping_tax_excluded
        if shipping_total:
            if binding.odoo_id.carrier_id:
                binding.odoo_id._create_delivery_line(
                    binding.odoo_id.carrier_id, shipping_total
                )
            binding.odoo_id.recompute()

    def _add_fee_line(self, binding):
        record = self.woo_record
        for fee_line in record.get("fee_lines"):
            total_fee = fee_line.get("total")
            so_description = fee_line.get("name")
            fee_product = binding.backend_id.fee_product_id
            values = {
                "order_id": binding.odoo_id.id,
                "name": so_description,
                "product_uom_qty": 1,
                "product_uom": fee_product.uom_id.id,
                "product_id": fee_product.id,
                "price_unit": total_fee,
            }
            if binding.odoo_id.order_line:
                values["sequence"] = binding.odoo_id.order_line[-1].sequence + 1
            self.env["sale.order.line"].sudo().create(values)
        binding.odoo_id.recompute()

    def _after_import(self, binding):
        super(SaleOrderImporter, self)._after_import(binding)
        self._add_shipping_line(binding)
        self._add_fee_line(binding)


class SaleOrderImportMapper(Component):
    _name = "woocommerce.sale.order.mapper"
    _inherit = "woocommerce.import.mapper"
    _apply_on = "woo.sale.order"

    direct = [
        ("number", "name"),
        ("customer_note", "note"),
        ("shipping_total", "total_shipping_tax_excluded"),
        ("total", "total_amount"),
        ("total_tax", "total_amount_tax"),
    ]

    children = [("items", "woo_order_line_ids", "woo.sale.order.line")]

    @mapping
    def status(self, record):
        if record["status"]:
            status_id = self.env["woo.sale.order.status"].search(
                [("name", "=", record["status"])]
            )
            if status_id:
                return {"status_id": status_id[0].id}
            else:
                status_id = self.env["woo.sale.order.status"].create(
                    {"name": record["status"]}
                )
                return {"status_id": status_id.id}
        else:
            return {"status_id": False}

    @mapping
    def customer_id(self, record):
        binder = self.binder_for("woo.res.partner")
        if record["customer_id"]:
            partner = binder.to_internal(record["customer_id"], unwrap=True) or False
            assert (
                partner
            ), "Please Check Customer Role \
                                in WooCommerce"
            shipping_address = (
                binder.to_internal(
                    str(record["customer_id"]) + "_shipping", unwrap=True
                )
                or False
            )
            assert (
                shipping_address
            ), "Please Check Customer Role \
                                in WooCommerce"
            result = {
                "partner_id": partner.id,
                "partner_shipping_id": shipping_address.id,
            }
        else:
            customer = record["billing"]
            country_id = False
            state_id = False
            if customer["country"]:
                country_id = self.env["res.country"].search(
                    [("code", "=", customer["country"])]
                )
                if country_id:
                    country_id = country_id.id
            if customer["state"]:
                state_id = self.env["res.country.state"].search(
                    [("code", "=", customer["state"]), ("country_id", "=", country_id)],
                    limit=1,
                )
                if state_id:
                    state_id = state_id.id
            name = customer["first_name"] + " " + customer["last_name"]
            partner_dict = {
                "name": name,
                "city": customer["city"],
                "phone": customer["phone"],
                "zip": customer["postcode"],
                "state_id": state_id,
                "country_id": country_id,
            }
            partner_id = self.env["res.partner"].create(partner_dict)

            # shipping
            shipping = record["shipping"]
            country_id = False
            state_id = False
            if shipping["country"]:
                country_id = self.env["res.country"].search(
                    [("code", "=", shipping["country"])]
                )
                if country_id:
                    country_id = country_id.id
            if shipping["state"]:
                state_id = self.env["res.country.state"].search(
                    [("code", "=", shipping["state"]), ("country_id", "=", country_id)],
                    limit=1,
                )
                if state_id:
                    state_id = state_id.id
            name = shipping["first_name"] + " " + shipping["last_name"]
            partner_dict = {
                "name": name,
                "city": shipping["city"],
                "zip": shipping["postcode"],
                "state_id": state_id,
                "country_id": country_id,
                "type": "delivery",
                "parent_id": partner_id.id,
            }
            shipping_partner = self.env["res.partner"].create(partner_dict)
            result = {
                "partner_id": partner_id.id,
                "shipping_partner": shipping_partner.id,
            }
        return result

    @mapping
    def payment(self, record):
        binder = self.binder_for("account.payment.mode")
        mode = binder.to_internal(record["payment_method"])
        assert mode, (
            "import of error fail in SaleImportRule.check "
            "when the payment mode is missing"
        )
        return {"payment_mode_id": mode.id}

    @mapping
    def carrier_id(self, record):
        if not record.get("shipping_lines"):
            return {}
        binder = self.binder_for("woo.delivery.carrier")
        carrier = binder.to_internal(
            record["shipping_lines"][0]["method_id"], unwrap=True
        )
        return {"carrier_id": carrier.id}

    @mapping
    def sale_team(self, record):
        if self.backend_record.sale_team_id:
            return {'team_id': self.backend_record.sale_team_id.id}

    @mapping
    def backend_id(self, record):
        return {"backend_id": self.backend_record.id}

    def finalize(self, map_record, values):
        onchange = self.component("ecommerce.onchange.manager.sale.order")
        return onchange.play(values, values["woo_order_line_ids"])


class SaleOrderLineImportMapper(Component):
    _name = "woocommerce.sale.order.line.mapper"
    _inherit = "woocommerce.import.mapper"
    _apply_on = "woo.sale.order.line"

    direct = [
        ("quantity", "product_uom_qty"),
        ("name", "name"),
        ("price", "price_unit"),
    ]

    @mapping
    def product_id(self, record):
        binder = self.binder_for("woo.product.template")
        product = binder.to_internal(record["product_id"], unwrap=True)
        assert product is not None, (
            "product_id %s should have been imported in "
            "SaleOrderImporter._import_dependencies" % record["product_id"]
        )
        return {"product_id": product.product_variant_ids.id}
