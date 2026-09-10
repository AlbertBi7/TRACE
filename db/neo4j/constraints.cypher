// TRACE Neo4j Constraints & Indexes
// Run once on fresh database to enforce data integrity.

// ─── Uniqueness Constraints ─────────────────────────────
CREATE CONSTRAINT person_entity_id IF NOT EXISTS
FOR (p:Person) REQUIRE p.entity_id IS UNIQUE;

CREATE CONSTRAINT org_entity_id IF NOT EXISTS
FOR (o:Org) REQUIRE o.entity_id IS UNIQUE;

CREATE CONSTRAINT location_entity_id IF NOT EXISTS
FOR (l:Location) REQUIRE l.entity_id IS UNIQUE;

CREATE CONSTRAINT phone_entity_id IF NOT EXISTS
FOR (p:Phone) REQUIRE p.entity_id IS UNIQUE;

CREATE CONSTRAINT vehicle_entity_id IF NOT EXISTS
FOR (v:Vehicle) REQUIRE v.entity_id IS UNIQUE;

CREATE CONSTRAINT bank_account_entity_id IF NOT EXISTS
FOR (b:BankAccount) REQUIRE b.entity_id IS UNIQUE;

// ─── Indexes for Common Queries ─────────────────────────
CREATE INDEX person_case_id IF NOT EXISTS FOR (p:Person) ON (p.case_id);
CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name);

CREATE INDEX org_case_id IF NOT EXISTS FOR (o:Org) ON (o.case_id);
CREATE INDEX org_name IF NOT EXISTS FOR (o:Org) ON (o.name);

CREATE INDEX location_case_id IF NOT EXISTS FOR (l:Location) ON (l.case_id);
CREATE INDEX location_name IF NOT EXISTS FOR (l:Location) ON (l.name);

CREATE INDEX phone_case_id IF NOT EXISTS FOR (p:Phone) ON (p.case_id);
CREATE INDEX phone_number IF NOT EXISTS FOR (p:Phone) ON (p.number);

CREATE INDEX vehicle_case_id IF NOT EXISTS FOR (v:Vehicle) ON (v.case_id);
CREATE INDEX vehicle_plate IF NOT EXISTS FOR (v:Vehicle) ON (v.plate);

CREATE INDEX bank_case_id IF NOT EXISTS FOR (b:BankAccount) ON (b.case_id);
CREATE INDEX bank_number IF NOT EXISTS FOR (b:BankAccount) ON (b.account_number);
