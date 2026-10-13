"""Initial manual-record schema for Supplier-Invoice-Verification.

Revision ID: 0001_manual_records
Revises: None
Schema only: no workspaces or business seed data.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_manual_records"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('workspaces',
    sa.Column('slug', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("name <> '' AND name = regexp_replace(name, '^[[:space:]]+|[[:space:]]+$', '', 'g')", name='ck_workspaces_name_text'),
    sa.CheckConstraint("slug <> '' AND slug = regexp_replace(slug, '^[[:space:]]+|[[:space:]]+$', '', 'g')", name='ck_workspaces_slug_text'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_workspaces')),
    sa.UniqueConstraint('slug', name='uq_workspaces_slug')
    )
    op.create_table('suppliers',
    sa.Column('supplier_code', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('notes', sa.String(length=2000), nullable=True),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("name <> '' AND name = regexp_replace(name, '^[[:space:]]+|[[:space:]]+$', '', 'g')", name='ck_suppliers_name_text'),
    sa.CheckConstraint("notes IS NULL OR (notes <> '' AND notes = regexp_replace(notes, '^[[:space:]]+|[[:space:]]+$', '', 'g'))", name='ck_suppliers_notes_text'),
    sa.CheckConstraint("supplier_code <> '' AND supplier_code = regexp_replace(supplier_code, '^[[:space:]]+|[[:space:]]+$', '', 'g')", name='ck_suppliers_supplier_code_text'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_suppliers_workspace', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_suppliers')),
    sa.UniqueConstraint('workspace_id', 'id', name='uq_suppliers_workspace_id'),
    sa.UniqueConstraint('workspace_id', 'supplier_code', name='uq_suppliers_code')
    )
    op.create_index('ix_suppliers_workspace_created_id', 'suppliers', ['workspace_id', 'created_at', 'id'], unique=False)
    op.create_table('purchase_orders',
    sa.Column('supplier_id', sa.UUID(), nullable=False),
    sa.Column('po_number', sa.String(length=64), nullable=False),
    sa.Column('order_date', sa.Date(), nullable=False),
    sa.Column('currency', sa.CHAR(length=3), nullable=False),
    sa.Column('notes', sa.String(length=2000), nullable=True),
    sa.Column('subtotal', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("currency = 'EUR'", name='ck_purchase_orders_currency'),
    sa.CheckConstraint("notes IS NULL OR (notes <> '' AND notes = regexp_replace(notes, '^[[:space:]]+|[[:space:]]+$', '', 'g'))", name='ck_purchase_orders_notes_text'),
    sa.CheckConstraint("order_date BETWEEN DATE '0001-01-01' AND DATE '9999-12-31'", name='ck_purchase_orders_order_date_range'),
    sa.CheckConstraint("po_number <> '' AND po_number = regexp_replace(po_number, '^[[:space:]]+|[[:space:]]+$', '', 'g')", name='ck_purchase_orders_po_number_text'),
    sa.CheckConstraint('subtotal >= 0 AND subtotal <= 9999999999999999.99', name='ck_purchase_orders_subtotal_range'),
    sa.ForeignKeyConstraint(['workspace_id', 'supplier_id'], ['suppliers.workspace_id', 'suppliers.id'], name='fk_purchase_orders_supplier', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_purchase_orders_workspace', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_purchase_orders')),
    sa.UniqueConstraint('workspace_id', 'id', name='uq_purchase_orders_workspace_id'),
    sa.UniqueConstraint('workspace_id', 'po_number', name='uq_purchase_orders_number'),
    sa.UniqueConstraint('workspace_id', 'supplier_id', 'id', name='uq_purchase_orders_supplier_id')
    )
    op.create_index('ix_purchase_orders_supplier', 'purchase_orders', ['workspace_id', 'supplier_id'], unique=False)
    op.create_index('ix_purchase_orders_workspace_created_id', 'purchase_orders', ['workspace_id', 'created_at', 'id'], unique=False)
    op.create_table('delivery_receipts',
    sa.Column('purchase_order_id', sa.UUID(), nullable=False),
    sa.Column('receipt_number', sa.String(length=64), nullable=False),
    sa.Column('received_date', sa.Date(), nullable=False),
    sa.Column('notes', sa.String(length=2000), nullable=True),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("notes IS NULL OR (notes <> '' AND notes = regexp_replace(notes, '^[[:space:]]+|[[:space:]]+$', '', 'g'))", name='ck_delivery_receipts_notes_text'),
    sa.CheckConstraint("receipt_number <> '' AND receipt_number = regexp_replace(receipt_number, '^[[:space:]]+|[[:space:]]+$', '', 'g')", name='ck_delivery_receipts_receipt_number_text'),
    sa.CheckConstraint("received_date BETWEEN DATE '0001-01-01' AND DATE '9999-12-31'", name='ck_delivery_receipts_received_date_range'),
    sa.ForeignKeyConstraint(['workspace_id', 'purchase_order_id'], ['purchase_orders.workspace_id', 'purchase_orders.id'], name='fk_delivery_receipts_order', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_delivery_receipts_workspace', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_delivery_receipts')),
    sa.UniqueConstraint('workspace_id', 'id', 'purchase_order_id', name='uq_delivery_receipts_order_id'),
    sa.UniqueConstraint('workspace_id', 'id', name='uq_delivery_receipts_workspace_id'),
    sa.UniqueConstraint('workspace_id', 'receipt_number', name='uq_delivery_receipts_number')
    )
    op.create_index('ix_delivery_receipts_order', 'delivery_receipts', ['workspace_id', 'purchase_order_id'], unique=False)
    op.create_index('ix_delivery_receipts_workspace_created_id', 'delivery_receipts', ['workspace_id', 'created_at', 'id'], unique=False)
    op.create_table('invoices',
    sa.Column('supplier_id', sa.UUID(), nullable=False),
    sa.Column('purchase_order_id', sa.UUID(), nullable=True),
    sa.Column('invoice_number', sa.String(length=64), nullable=False),
    sa.Column('invoice_date', sa.Date(), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('currency', sa.CHAR(length=3), nullable=False),
    sa.Column('status', sa.String(length=16), server_default=sa.text("'draft'"), nullable=False),
    sa.Column('notes', sa.String(length=2000), nullable=True),
    sa.Column('subtotal', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('tax_amount', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('total', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("currency = 'EUR'", name='ck_invoices_currency'),
    sa.CheckConstraint("due_date IS NULL OR (due_date BETWEEN DATE '0001-01-01' AND DATE '9999-12-31')", name='ck_invoices_due_date_range'),
    sa.CheckConstraint("invoice_date BETWEEN DATE '0001-01-01' AND DATE '9999-12-31'", name='ck_invoices_invoice_date_range'),
    sa.CheckConstraint("invoice_number <> '' AND invoice_number = regexp_replace(invoice_number, '^[[:space:]]+|[[:space:]]+$', '', 'g')", name='ck_invoices_invoice_number_text'),
    sa.CheckConstraint("notes IS NULL OR (notes <> '' AND notes = regexp_replace(notes, '^[[:space:]]+|[[:space:]]+$', '', 'g'))", name='ck_invoices_notes_text'),
    sa.CheckConstraint("status = 'draft'", name='ck_invoices_status'),
    sa.CheckConstraint('due_date IS NULL OR due_date >= invoice_date', name='ck_invoices_due_date'),
    sa.CheckConstraint('subtotal >= 0 AND subtotal <= 9999999999999999.99', name='ck_invoices_subtotal_range'),
    sa.CheckConstraint('tax_amount >= 0 AND tax_amount <= 9999999999999999.99', name='ck_invoices_tax_amount_range'),
    sa.CheckConstraint('total = subtotal + tax_amount', name='ck_invoices_total'),
    sa.CheckConstraint('total >= 0 AND total <= 9999999999999999.99', name='ck_invoices_total_range'),
    sa.ForeignKeyConstraint(['workspace_id', 'supplier_id', 'purchase_order_id'], ['purchase_orders.workspace_id', 'purchase_orders.supplier_id', 'purchase_orders.id'], name='fk_invoices_supplier_order', ondelete='RESTRICT', match='SIMPLE'),
    sa.ForeignKeyConstraint(['workspace_id', 'supplier_id'], ['suppliers.workspace_id', 'suppliers.id'], name='fk_invoices_supplier', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_invoices_workspace', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_invoices')),
    sa.UniqueConstraint('workspace_id', 'id', 'purchase_order_id', name='uq_invoices_order_id'),
    sa.UniqueConstraint('workspace_id', 'id', name='uq_invoices_workspace_id'),
    sa.UniqueConstraint('workspace_id', 'supplier_id', 'invoice_number', name='uq_invoices_supplier_number')
    )
    op.create_index('ix_invoices_order', 'invoices', ['workspace_id', 'purchase_order_id'], unique=False)
    op.create_index('ix_invoices_workspace_created_id', 'invoices', ['workspace_id', 'created_at', 'id'], unique=False)
    op.create_table('purchase_order_lines',
    sa.Column('purchase_order_id', sa.UUID(), nullable=False),
    sa.Column('line_no', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=14, scale=4), nullable=False),
    sa.Column('line_total', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("description <> '' AND description = regexp_replace(description, '^[[:space:]]+|[[:space:]]+$', '', 'g')", name='ck_purchase_order_lines_description_text'),
    sa.CheckConstraint('line_no > 0', name='ck_order_lines_line_no'),
    sa.CheckConstraint('line_total >= 0 AND line_total <= 9999999999999999.99', name='ck_purchase_order_lines_line_total_range'),
    sa.CheckConstraint('quantity > 0 AND quantity <= 999999999.999', name='ck_purchase_order_lines_quantity_range'),
    sa.CheckConstraint('unit_price >= 0 AND unit_price <= 9999999999.9999', name='ck_purchase_order_lines_unit_price_range'),
    sa.ForeignKeyConstraint(['workspace_id', 'purchase_order_id'], ['purchase_orders.workspace_id', 'purchase_orders.id'], name='fk_order_lines_order', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_purchase_order_lines_workspace', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_purchase_order_lines')),
    sa.UniqueConstraint('workspace_id', 'id', name='uq_purchase_order_lines_workspace_id'),
    sa.UniqueConstraint('workspace_id', 'purchase_order_id', 'id', name='uq_order_lines_order_id'),
    sa.UniqueConstraint('workspace_id', 'purchase_order_id', 'line_no', name='uq_order_lines_line_no')
    )
    op.create_index('ix_purchase_order_lines_workspace_created_id', 'purchase_order_lines', ['workspace_id', 'created_at', 'id'], unique=False)
    op.create_table('delivery_receipt_lines',
    sa.Column('delivery_receipt_id', sa.UUID(), nullable=False),
    sa.Column('purchase_order_id', sa.UUID(), nullable=False),
    sa.Column('purchase_order_line_id', sa.UUID(), nullable=False),
    sa.Column('line_no', sa.Integer(), nullable=False),
    sa.Column('quantity_received', sa.Numeric(precision=12, scale=3), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint('line_no > 0', name='ck_receipt_lines_line_no'),
    sa.CheckConstraint('quantity_received > 0 AND quantity_received <= 999999999.999', name='ck_delivery_receipt_lines_quantity_received_range'),
    sa.ForeignKeyConstraint(['workspace_id', 'delivery_receipt_id', 'purchase_order_id'], ['delivery_receipts.workspace_id', 'delivery_receipts.id', 'delivery_receipts.purchase_order_id'], name='fk_receipt_lines_receipt_order', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['workspace_id', 'purchase_order_id', 'purchase_order_line_id'], ['purchase_order_lines.workspace_id', 'purchase_order_lines.purchase_order_id', 'purchase_order_lines.id'], name='fk_receipt_lines_order_line', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_delivery_receipt_lines_workspace', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_delivery_receipt_lines')),
    sa.UniqueConstraint('workspace_id', 'delivery_receipt_id', 'line_no', name='uq_receipt_lines_line_no'),
    sa.UniqueConstraint('workspace_id', 'delivery_receipt_id', 'purchase_order_line_id', name='uq_receipt_lines_order_line'),
    sa.UniqueConstraint('workspace_id', 'id', name='uq_delivery_receipt_lines_workspace_id')
    )
    op.create_index('ix_delivery_receipt_lines_workspace_created_id', 'delivery_receipt_lines', ['workspace_id', 'created_at', 'id'], unique=False)
    op.create_index('ix_receipt_lines_order_line', 'delivery_receipt_lines', ['workspace_id', 'purchase_order_id', 'purchase_order_line_id'], unique=False)
    op.create_table('invoice_lines',
    sa.Column('invoice_id', sa.UUID(), nullable=False),
    sa.Column('line_no', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=14, scale=4), nullable=False),
    sa.Column('line_total', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('purchase_order_line_id', sa.UUID(), nullable=True),
    sa.Column('purchase_order_id', sa.UUID(), nullable=True),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("description <> '' AND description = regexp_replace(description, '^[[:space:]]+|[[:space:]]+$', '', 'g')", name='ck_invoice_lines_description_text'),
    sa.CheckConstraint('(purchase_order_id IS NULL) = (purchase_order_line_id IS NULL)', name='ck_invoice_lines_mapping_pair'),
    sa.CheckConstraint('line_no > 0', name='ck_invoice_lines_line_no'),
    sa.CheckConstraint('line_total >= 0 AND line_total <= 9999999999999999.99', name='ck_invoice_lines_line_total_range'),
    sa.CheckConstraint('quantity > 0 AND quantity <= 999999999.999', name='ck_invoice_lines_quantity_range'),
    sa.CheckConstraint('unit_price >= 0 AND unit_price <= 9999999999.9999', name='ck_invoice_lines_unit_price_range'),
    sa.ForeignKeyConstraint(['workspace_id', 'invoice_id', 'purchase_order_id'], ['invoices.workspace_id', 'invoices.id', 'invoices.purchase_order_id'], name='fk_invoice_lines_invoice_order', ondelete='RESTRICT', match='SIMPLE'),
    sa.ForeignKeyConstraint(['workspace_id', 'invoice_id'], ['invoices.workspace_id', 'invoices.id'], name='fk_invoice_lines_invoice', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['workspace_id', 'purchase_order_id', 'purchase_order_line_id'], ['purchase_order_lines.workspace_id', 'purchase_order_lines.purchase_order_id', 'purchase_order_lines.id'], name='fk_invoice_lines_order_line', ondelete='RESTRICT', match='SIMPLE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_invoice_lines_workspace', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_invoice_lines')),
    sa.UniqueConstraint('workspace_id', 'id', name='uq_invoice_lines_workspace_id'),
    sa.UniqueConstraint('workspace_id', 'invoice_id', 'line_no', name='uq_invoice_lines_line_no')
    )
    op.create_index('ix_invoice_lines_order_line', 'invoice_lines', ['workspace_id', 'purchase_order_id', 'purchase_order_line_id'], unique=False)
    op.create_index('ix_invoice_lines_workspace_created_id', 'invoice_lines', ['workspace_id', 'created_at', 'id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_invoice_lines_workspace_created_id', table_name='invoice_lines')
    op.drop_index('ix_invoice_lines_order_line', table_name='invoice_lines')
    op.drop_table('invoice_lines')
    op.drop_index('ix_receipt_lines_order_line', table_name='delivery_receipt_lines')
    op.drop_index('ix_delivery_receipt_lines_workspace_created_id', table_name='delivery_receipt_lines')
    op.drop_table('delivery_receipt_lines')
    op.drop_index('ix_purchase_order_lines_workspace_created_id', table_name='purchase_order_lines')
    op.drop_table('purchase_order_lines')
    op.drop_index('ix_invoices_workspace_created_id', table_name='invoices')
    op.drop_index('ix_invoices_order', table_name='invoices')
    op.drop_table('invoices')
    op.drop_index('ix_delivery_receipts_workspace_created_id', table_name='delivery_receipts')
    op.drop_index('ix_delivery_receipts_order', table_name='delivery_receipts')
    op.drop_table('delivery_receipts')
    op.drop_index('ix_purchase_orders_workspace_created_id', table_name='purchase_orders')
    op.drop_index('ix_purchase_orders_supplier', table_name='purchase_orders')
    op.drop_table('purchase_orders')
    op.drop_index('ix_suppliers_workspace_created_id', table_name='suppliers')
    op.drop_table('suppliers')
    op.drop_table('workspaces')
