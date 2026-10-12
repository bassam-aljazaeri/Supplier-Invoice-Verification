from app.schemas.common import CreateModel, Identifier, Name, Notes, ReadRecord, RecordList


class SupplierCreate(CreateModel):
    supplier_code: Identifier
    name: Name
    notes: Notes = None


class SupplierRead(ReadRecord):
    supplier_code: str
    name: str
    notes: str | None


class SupplierList(RecordList[SupplierRead]):
    pass
