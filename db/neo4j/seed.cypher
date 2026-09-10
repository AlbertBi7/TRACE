// TRACE Neo4j Seed Graph — Operation Nexus (Fictional Financial Fraud Ring)
// All names, numbers, and details are entirely fictional / anonymized.
// This graph is for demo purposes only — it does not represent real individuals.
//
// IMPORTANT: this file uses the SAME schema the API reads/writes (Milestone 5):
//   (:Entity {entity_id, name, entity_type, aliases, provenance_ids, case_ids})
//   (:Entity)-[:LINKED {relation, provenance_ids, case_ids, observations}]->(:Entity)
// Every statement is self-contained (cypher-shell does NOT carry variables across
// statements) and MERGE-based, so re-running this file is idempotent. The compose
// `neo4j-init` service also clears the demo case first (see docker-compose.yml),
// so the demo graph always matches this checked-in fixture exactly.
// Demo case id: c0000000-0000-0000-0000-000000000001

// ─── Persons ─────────────────────────────────────────────
MERGE (p1:Entity {entity_id: 'PER-001'}) SET p1.name = 'Rohan Mehra', p1.entity_type = 'PERSON', p1.aliases = ['R. Mehra', 'Rohan M.'], p1.provenance_ids = ['ext-001'], p1.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (p2:Entity {entity_id: 'PER-002'}) SET p2.name = 'Priya Sharma', p2.entity_type = 'PERSON', p2.aliases = ['P. Sharma'], p2.provenance_ids = ['ext-002'], p2.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (p3:Entity {entity_id: 'PER-003'}) SET p3.name = 'Vikram Singh', p3.entity_type = 'PERSON', p3.aliases = ['V. Singh', 'Vicky'], p3.provenance_ids = ['ext-003'], p3.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (p4:Entity {entity_id: 'PER-004'}) SET p4.name = 'Anita Desai', p4.entity_type = 'PERSON', p4.aliases = ['A. Desai'], p4.provenance_ids = ['ext-004'], p4.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (p5:Entity {entity_id: 'PER-005'}) SET p5.name = 'Suresh Patel', p5.entity_type = 'PERSON', p5.aliases = ['S. Patel'], p5.provenance_ids = ['ext-005'], p5.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (p6:Entity {entity_id: 'PER-006'}) SET p6.name = 'Kavita Nair', p6.entity_type = 'PERSON', p6.aliases = ['K. Nair'], p6.provenance_ids = ['ext-006'], p6.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (p7:Entity {entity_id: 'PER-007'}) SET p7.name = 'Deepak Joshi', p7.entity_type = 'PERSON', p7.aliases = ['D. Joshi'], p7.provenance_ids = ['ext-007'], p7.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (p8:Entity {entity_id: 'PER-008'}) SET p8.name = 'Meena Kulkarni', p8.entity_type = 'PERSON', p8.aliases = ['M. Kulkarni'], p8.provenance_ids = ['ext-008'], p8.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (p9:Entity {entity_id: 'PER-009'}) SET p9.name = 'Arjun Reddy', p9.entity_type = 'PERSON', p9.aliases = ['A. Reddy'], p9.provenance_ids = ['ext-009'], p9.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (p10:Entity {entity_id: 'PER-010'}) SET p10.name = 'Fatima Khan', p10.entity_type = 'PERSON', p10.aliases = ['F. Khan'], p10.provenance_ids = ['ext-010'], p10.case_ids = ['c0000000-0000-0000-0000-000000000001'];

// ─── Organizations ───────────────────────────────────────
MERGE (o1:Entity {entity_id: 'ORG-001'}) SET o1.name = 'Nexus Trading Corp', o1.entity_type = 'ORG', o1.aliases = ['NTC', 'Nexus Trading'], o1.provenance_ids = ['ext-011'], o1.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (o2:Entity {entity_id: 'ORG-002'}) SET o2.name = 'Emerald Logistics Pvt Ltd', o2.entity_type = 'ORG', o2.aliases = ['Emerald Logistics'], o2.provenance_ids = ['ext-012'], o2.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (o3:Entity {entity_id: 'ORG-003'}) SET o3.name = 'Sunrise Consulting', o3.entity_type = 'ORG', o3.aliases = ['Sunrise Consult'], o3.provenance_ids = ['ext-013'], o3.case_ids = ['c0000000-0000-0000-0000-000000000001'];

// ─── Locations ───────────────────────────────────────────
MERGE (l1:Entity {entity_id: 'LOC-001'}) SET l1.name = 'Mumbai, Maharashtra', l1.entity_type = 'LOCATION', l1.aliases = [], l1.provenance_ids = ['ext-014'], l1.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (l2:Entity {entity_id: 'LOC-002'}) SET l2.name = 'Delhi NCR', l2.entity_type = 'LOCATION', l2.aliases = [], l2.provenance_ids = ['ext-015'], l2.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (l3:Entity {entity_id: 'LOC-003'}) SET l3.name = 'Bengaluru, Karnataka', l3.entity_type = 'LOCATION', l3.aliases = [], l3.provenance_ids = ['ext-016'], l3.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (l4:Entity {entity_id: 'LOC-004'}) SET l4.name = 'Hyderabad, Telangana', l4.entity_type = 'LOCATION', l4.aliases = [], l4.provenance_ids = ['ext-017'], l4.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (l5:Entity {entity_id: 'LOC-005'}) SET l5.name = 'Chennai, Tamil Nadu', l5.entity_type = 'LOCATION', l5.aliases = [], l5.provenance_ids = ['ext-018'], l5.case_ids = ['c0000000-0000-0000-0000-000000000001'];

// ─── Phones ──────────────────────────────────────────────
MERGE (ph1:Entity {entity_id: 'PHN-001'}) SET ph1.name = '+91-98765-43210', ph1.entity_type = 'PHONE', ph1.aliases = [], ph1.provenance_ids = ['ext-019'], ph1.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (ph2:Entity {entity_id: 'PHN-002'}) SET ph2.name = '+91-98765-43211', ph2.entity_type = 'PHONE', ph2.aliases = [], ph2.provenance_ids = ['ext-020'], ph2.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (ph3:Entity {entity_id: 'PHN-003'}) SET ph3.name = '+91-99887-76655', ph3.entity_type = 'PHONE', ph3.aliases = [], ph3.provenance_ids = ['ext-021'], ph3.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (ph4:Entity {entity_id: 'PHN-004'}) SET ph4.name = '+91-91234-56789', ph4.entity_type = 'PHONE', ph4.aliases = [], ph4.provenance_ids = ['ext-022'], ph4.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (ph5:Entity {entity_id: 'PHN-005'}) SET ph5.name = '+91-88776-65544', ph5.entity_type = 'PHONE', ph5.aliases = [], ph5.provenance_ids = ['ext-023'], ph5.case_ids = ['c0000000-0000-0000-0000-000000000001'];

// ─── Vehicles ────────────────────────────────────────────
MERGE (v1:Entity {entity_id: 'VEH-001'}) SET v1.name = 'MH-02-AB-1234', v1.entity_type = 'VEHICLE', v1.aliases = [], v1.provenance_ids = ['ext-024'], v1.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (v2:Entity {entity_id: 'VEH-002'}) SET v2.name = 'DL-01-CD-5678', v2.entity_type = 'VEHICLE', v2.aliases = [], v2.provenance_ids = ['ext-025'], v2.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (v3:Entity {entity_id: 'VEH-003'}) SET v3.name = 'KA-05-EF-9012', v3.entity_type = 'VEHICLE', v3.aliases = [], v3.provenance_ids = ['ext-026'], v3.case_ids = ['c0000000-0000-0000-0000-000000000001'];

// ─── Bank Accounts ───────────────────────────────────────
MERGE (ba1:Entity {entity_id: 'BA-001'}) SET ba1.name = 'HDFC-XXXX-4521', ba1.entity_type = 'BANK_ACCOUNT', ba1.aliases = [], ba1.provenance_ids = ['ext-027'], ba1.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (ba2:Entity {entity_id: 'BA-002'}) SET ba2.name = 'SBI-XXXX-7832', ba2.entity_type = 'BANK_ACCOUNT', ba2.aliases = [], ba2.provenance_ids = ['ext-028'], ba2.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (ba3:Entity {entity_id: 'BA-003'}) SET ba3.name = 'ICICI-XXXX-1199', ba3.entity_type = 'BANK_ACCOUNT', ba3.aliases = [], ba3.provenance_ids = ['ext-029'], ba3.case_ids = ['c0000000-0000-0000-0000-000000000001'];
MERGE (ba4:Entity {entity_id: 'BA-004'}) SET ba4.name = 'AXIS-XXXX-6650', ba4.entity_type = 'BANK_ACCOUNT', ba4.aliases = [], ba4.provenance_ids = ['ext-030'], ba4.case_ids = ['c0000000-0000-0000-0000-000000000001'];

// ─── Person–Phone associations ───────────────────────────
MERGE (p1:Entity {entity_id: 'PER-001'}) MERGE (ph1:Entity {entity_id: 'PHN-001'}) MERGE (p1)-[r:LINKED {relation: 'ASSOCIATED_WITH'}]->(ph1) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-031'], r.observations = 1;
MERGE (p2:Entity {entity_id: 'PER-002'}) MERGE (ph2:Entity {entity_id: 'PHN-002'}) MERGE (p2)-[r:LINKED {relation: 'ASSOCIATED_WITH'}]->(ph2) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-032'], r.observations = 1;
MERGE (p3:Entity {entity_id: 'PER-003'}) MERGE (ph3:Entity {entity_id: 'PHN-003'}) MERGE (p3)-[r:LINKED {relation: 'ASSOCIATED_WITH'}]->(ph3) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-033'], r.observations = 1;
MERGE (p5:Entity {entity_id: 'PER-005'}) MERGE (ph4:Entity {entity_id: 'PHN-004'}) MERGE (p5)-[r:LINKED {relation: 'ASSOCIATED_WITH'}]->(ph4) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-034'], r.observations = 1;
MERGE (p7:Entity {entity_id: 'PER-007'}) MERGE (ph5:Entity {entity_id: 'PHN-005'}) MERGE (p7)-[r:LINKED {relation: 'ASSOCIATED_WITH'}]->(ph5) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-035'], r.observations = 1;

// ─── Call records ────────────────────────────────────────
MERGE (ph1:Entity {entity_id: 'PHN-001'}) MERGE (ph2:Entity {entity_id: 'PHN-002'}) MERGE (ph1)-[r:LINKED {relation: 'CALLED'}]->(ph2) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-036'], r.observations = 47;
MERGE (ph1:Entity {entity_id: 'PHN-001'}) MERGE (ph3:Entity {entity_id: 'PHN-003'}) MERGE (ph1)-[r:LINKED {relation: 'CALLED'}]->(ph3) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-037'], r.observations = 23;
MERGE (ph2:Entity {entity_id: 'PHN-002'}) MERGE (ph4:Entity {entity_id: 'PHN-004'}) MERGE (ph2)-[r:LINKED {relation: 'CALLED'}]->(ph4) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-038'], r.observations = 12;
MERGE (ph3:Entity {entity_id: 'PHN-003'}) MERGE (ph5:Entity {entity_id: 'PHN-005'}) MERGE (ph3)-[r:LINKED {relation: 'CALLED'}]->(ph5) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-039'], r.observations = 31;

// ─── Financial transfers ─────────────────────────────────
MERGE (ba1:Entity {entity_id: 'BA-001'}) MERGE (ba2:Entity {entity_id: 'BA-002'}) MERGE (ba1)-[r:LINKED {relation: 'TRANSFERRED_TO'}]->(ba2) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-040'], r.observations = 1;
MERGE (ba2:Entity {entity_id: 'BA-002'}) MERGE (ba3:Entity {entity_id: 'BA-003'}) MERGE (ba2)-[r:LINKED {relation: 'TRANSFERRED_TO'}]->(ba3) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-041'], r.observations = 1;
MERGE (ba3:Entity {entity_id: 'BA-003'}) MERGE (ba4:Entity {entity_id: 'BA-004'}) MERGE (ba3)-[r:LINKED {relation: 'TRANSFERRED_TO'}]->(ba4) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-042'], r.observations = 1;
MERGE (ba1:Entity {entity_id: 'BA-001'}) MERGE (ba4:Entity {entity_id: 'BA-004'}) MERGE (ba1)-[r:LINKED {relation: 'TRANSFERRED_TO'}]->(ba4) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-043'], r.observations = 1;

// ─── Person–BankAccount ownership ────────────────────────
MERGE (p1:Entity {entity_id: 'PER-001'}) MERGE (ba1:Entity {entity_id: 'BA-001'}) MERGE (p1)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'account_holder'}]->(ba1) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-044'], r.observations = 1;
MERGE (p3:Entity {entity_id: 'PER-003'}) MERGE (ba2:Entity {entity_id: 'BA-002'}) MERGE (p3)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'account_holder'}]->(ba2) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-045'], r.observations = 1;
MERGE (p4:Entity {entity_id: 'PER-004'}) MERGE (ba3:Entity {entity_id: 'BA-003'}) MERGE (p4)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'account_holder'}]->(ba3) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-046'], r.observations = 1;
MERGE (p6:Entity {entity_id: 'PER-006'}) MERGE (ba4:Entity {entity_id: 'BA-004'}) MERGE (p6)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'account_holder'}]->(ba4) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-047'], r.observations = 1;

// ─── Person–Org employment/association ───────────────────
MERGE (p1:Entity {entity_id: 'PER-001'}) MERGE (o1:Entity {entity_id: 'ORG-001'}) MERGE (p1)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'director'}]->(o1) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-048'], r.observations = 1;
MERGE (p2:Entity {entity_id: 'PER-002'}) MERGE (o1:Entity {entity_id: 'ORG-001'}) MERGE (p2)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'employee'}]->(o1) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-049'], r.observations = 1;
MERGE (p3:Entity {entity_id: 'PER-003'}) MERGE (o2:Entity {entity_id: 'ORG-002'}) MERGE (p3)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'owner'}]->(o2) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-050'], r.observations = 1;
MERGE (p5:Entity {entity_id: 'PER-005'}) MERGE (o2:Entity {entity_id: 'ORG-002'}) MERGE (p5)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'driver'}]->(o2) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-051'], r.observations = 1;
MERGE (p4:Entity {entity_id: 'PER-004'}) MERGE (o3:Entity {entity_id: 'ORG-003'}) MERGE (p4)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'partner'}]->(o3) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-052'], r.observations = 1;
MERGE (p6:Entity {entity_id: 'PER-006'}) MERGE (o3:Entity {entity_id: 'ORG-003'}) MERGE (p6)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'consultant'}]->(o3) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-053'], r.observations = 1;

// ─── Travel associations ─────────────────────────────────
MERGE (p1:Entity {entity_id: 'PER-001'}) MERGE (p3:Entity {entity_id: 'PER-003'}) MERGE (p1)-[r:LINKED {relation: 'TRAVELLED_WITH'}]->(p3) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-054'], r.observations = 1;
MERGE (p2:Entity {entity_id: 'PER-002'}) MERGE (p4:Entity {entity_id: 'PER-004'}) MERGE (p2)-[r:LINKED {relation: 'TRAVELLED_WITH'}]->(p4) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-055'], r.observations = 1;
MERGE (p5:Entity {entity_id: 'PER-005'}) MERGE (p7:Entity {entity_id: 'PER-007'}) MERGE (p5)-[r:LINKED {relation: 'TRAVELLED_WITH'}]->(p7) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-056'], r.observations = 1;

// ─── Person–Vehicle ──────────────────────────────────────
MERGE (p5:Entity {entity_id: 'PER-005'}) MERGE (v1:Entity {entity_id: 'VEH-001'}) MERGE (p5)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'driver'}]->(v1) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-057'], r.observations = 1;
MERGE (p7:Entity {entity_id: 'PER-007'}) MERGE (v2:Entity {entity_id: 'VEH-002'}) MERGE (p7)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'owner'}]->(v2) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-058'], r.observations = 1;
MERGE (p9:Entity {entity_id: 'PER-009'}) MERGE (v3:Entity {entity_id: 'VEH-003'}) MERGE (p9)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'registered_owner'}]->(v3) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-059'], r.observations = 1;

// ─── Person–Location ─────────────────────────────────────
MERGE (p1:Entity {entity_id: 'PER-001'}) MERGE (l1:Entity {entity_id: 'LOC-001'}) MERGE (p1)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'residence'}]->(l1) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-060'], r.observations = 1;
MERGE (p3:Entity {entity_id: 'PER-003'}) MERGE (l2:Entity {entity_id: 'LOC-002'}) MERGE (p3)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'residence'}]->(l2) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-061'], r.observations = 1;
MERGE (p4:Entity {entity_id: 'PER-004'}) MERGE (l3:Entity {entity_id: 'LOC-003'}) MERGE (p4)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'office'}]->(l3) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-062'], r.observations = 1;
MERGE (p9:Entity {entity_id: 'PER-009'}) MERGE (l4:Entity {entity_id: 'LOC-004'}) MERGE (p9)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'residence'}]->(l4) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-063'], r.observations = 1;
MERGE (p10:Entity {entity_id: 'PER-010'}) MERGE (l5:Entity {entity_id: 'LOC-005'}) MERGE (p10)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'residence'}]->(l5) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-064'], r.observations = 1;

// ─── Cross-links: Meena Kulkarni / Arjun Reddy / Fatima Khan ──
MERGE (p8:Entity {entity_id: 'PER-008'}) MERGE (p9:Entity {entity_id: 'PER-009'}) MERGE (p8)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'known_associate'}]->(p9) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-065'], r.observations = 1;
MERGE (p9:Entity {entity_id: 'PER-009'}) MERGE (p10:Entity {entity_id: 'PER-010'}) MERGE (p9)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'known_associate'}]->(p10) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-066'], r.observations = 1;
MERGE (p10:Entity {entity_id: 'PER-010'}) MERGE (o1:Entity {entity_id: 'ORG-001'}) MERGE (p10)-[r:LINKED {relation: 'ASSOCIATED_WITH', role: 'former_employee'}]->(o1) SET r.case_ids = ['c0000000-0000-0000-0000-000000000001'], r.provenance_ids = ['ext-067'], r.observations = 1;
