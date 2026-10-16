DO $$
DECLARE
    total_records CONSTANT INTEGER := 50000;
    payload_size_bytes CONSTANT INTEGER := 3072;
BEGIN
    FOR i IN 1..total_records LOOP
        INSERT INTO benchmark_payload (payload_data) 
        VALUES (repeat('A', payload_size_bytes));
    END LOOP;
END $$;
