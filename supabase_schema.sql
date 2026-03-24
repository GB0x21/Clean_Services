-- ============================================================
-- CleanFlow — Schema completo para Supabase
-- Ejecutar en SQL Editor de Supabase Dashboard
-- ============================================================

-- 1. OPPORTUNITIES (leads/oportunidades)
CREATE TABLE IF NOT EXISTS opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    source_url TEXT UNIQUE,
    source_platform TEXT,
    city TEXT,
    state TEXT,

    -- AI analysis fields
    client_type TEXT,
    client_name TEXT,
    service_types JSONB DEFAULT '[]',
    estimated_value NUMERIC(12,2),
    payment_terms_days INTEGER,
    is_recurring BOOLEAN DEFAULT false,
    deadline TEXT,
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    license_requirements INTEGER DEFAULT 0,
    urgency TEXT DEFAULT 'medium',
    confidence_score NUMERIC(3,2),
    opportunity_type TEXT,

    -- Scoring
    quality_score NUMERIC(5,1) DEFAULT 0,
    classification TEXT DEFAULT 'new',
    status TEXT DEFAULT 'new',

    -- Matching
    matched_subcontractor_id UUID,
    rejection_reason TEXT,
    ai_notes TEXT,

    -- Timestamps
    scraped_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT valid_status CHECK (status IN (
        'new', 'qualified', 'review', 'matched', 'bid_created',
        'sent', 'won', 'lost', 'cold', 'disqualified', 'no_match'
    )),
    CONSTRAINT valid_classification CHECK (classification IN (
        'new', 'hot', 'warm', 'cold'
    ))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_opp_status ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opp_city ON opportunities(city);
CREATE INDEX IF NOT EXISTS idx_opp_score ON opportunities(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_opp_scraped ON opportunities(scraped_at DESC);

-- Auto-update timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER opp_updated_at
    BEFORE UPDATE ON opportunities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- 2. SUBCONTRACTORS
CREATE TABLE IF NOT EXISTS subcontractors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name TEXT NOT NULL,
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    primary_city TEXT,
    state TEXT,
    services_offered JSONB DEFAULT '[]',
    pricing_model JSONB DEFAULT '{}',
    quality_score NUMERIC(3,1) DEFAULT 3.0,
    availability_status TEXT DEFAULT 'available',
    payment_terms_days INTEGER DEFAULT 30,
    minimum_job_size NUMERIC(10,2) DEFAULT 500,
    max_simultaneous_jobs INTEGER DEFAULT 5,
    current_jobs INTEGER DEFAULT 0,
    jobs_completed INTEGER DEFAULT 0,
    insurance_verified BOOLEAN DEFAULT false,
    workers_comp BOOLEAN DEFAULT false,
    background_check BOOLEAN DEFAULT false,
    status TEXT DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT valid_sub_status CHECK (status IN ('active', 'inactive', 'suspended')),
    CONSTRAINT valid_availability CHECK (availability_status IN ('available', 'limited', 'unavailable'))
);

CREATE INDEX IF NOT EXISTS idx_sub_city ON subcontractors(primary_city);
CREATE INDEX IF NOT EXISTS idx_sub_status ON subcontractors(status);

CREATE TRIGGER sub_updated_at
    BEFORE UPDATE ON subcontractors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- 3. BIDS (propuestas)
CREATE TABLE IF NOT EXISTS bids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id UUID REFERENCES opportunities(id) ON DELETE CASCADE,
    subcontractor_id UUID REFERENCES subcontractors(id),
    subcontractor_name TEXT,
    bid_amount NUMERIC(12,2),
    estimated_cost NUMERIC(12,2),
    estimated_margin NUMERIC(5,1),
    estimated_profit NUMERIC(12,2),
    match_score NUMERIC(4,3),
    cashflow_advantage_days INTEGER DEFAULT 0,
    proposal_text TEXT,
    email_subject TEXT,
    status TEXT DEFAULT 'draft',
    generated_by_ai BOOLEAN DEFAULT true,
    sent_at TIMESTAMPTZ,
    last_followup_number INTEGER DEFAULT 0,
    last_followup_date TIMESTAMPTZ,
    response_received_at TIMESTAMPTZ,
    response_type TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT valid_bid_status CHECK (status IN (
        'draft', 'approved', 'sent', 'cold', 'won', 'lost', 'withdrawn'
    ))
);

CREATE INDEX IF NOT EXISTS idx_bid_status ON bids(status);
CREATE INDEX IF NOT EXISTS idx_bid_opp ON bids(opportunity_id);

CREATE TRIGGER bid_updated_at
    BEFORE UPDATE ON bids
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- 4. SCRAPING LOGS
CREATE TABLE IF NOT EXISTS scraping_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_platform TEXT,
    queries_executed INTEGER DEFAULT 0,
    total_results INTEGER DEFAULT 0,
    filtered_results INTEGER DEFAULT 0,
    unique_results INTEGER DEFAULT 0,
    status TEXT DEFAULT 'completed',
    error_message TEXT,
    timestamp TIMESTAMPTZ DEFAULT now()
);


-- 5. FOLLOWUP LOGS
CREATE TABLE IF NOT EXISTS followup_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bid_id UUID REFERENCES bids(id) ON DELETE CASCADE,
    followup_number INTEGER,
    method TEXT,
    sent_at TIMESTAMPTZ DEFAULT now(),
    response_received BOOLEAN DEFAULT false,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_followup_bid ON followup_logs(bid_id);


-- 6. CONTRACT PERFORMANCE (para el monitor)
CREATE TABLE IF NOT EXISTS contract_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bid_id UUID REFERENCES bids(id),
    client_name TEXT,
    subcontractor_name TEXT,
    service_type TEXT,
    monthly_value NUMERIC(12,2),
    start_date DATE,
    quality_score NUMERIC(3,1),
    issues_count INTEGER DEFAULT 0,
    payment_status TEXT DEFAULT 'on_time',
    risk_level TEXT DEFAULT 'low',
    risk_factors JSONB DEFAULT '[]',
    last_check_date TIMESTAMPTZ,
    next_check_date TIMESTAMPTZ,
    ai_satisfaction_prediction NUMERIC(3,1),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER perf_updated_at
    BEFORE UPDATE ON contract_performance
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- 7. ROW LEVEL SECURITY (RLS)
ALTER TABLE opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE subcontractors ENABLE ROW LEVEL SECURITY;
ALTER TABLE bids ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraping_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE followup_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE contract_performance ENABLE ROW LEVEL SECURITY;

-- Políticas: permitir lectura pública para el frontend
CREATE POLICY "Public read opportunities" ON opportunities FOR SELECT USING (true);
CREATE POLICY "Public read subcontractors" ON subcontractors FOR SELECT USING (true);
CREATE POLICY "Public read bids" ON bids FOR SELECT USING (true);
CREATE POLICY "Public read scraping_logs" ON scraping_logs FOR SELECT USING (true);
CREATE POLICY "Public read contract_performance" ON contract_performance FOR SELECT USING (true);

-- Políticas: service_role puede hacer todo (para los agentes Python)
CREATE POLICY "Service insert opportunities" ON opportunities FOR INSERT WITH CHECK (true);
CREATE POLICY "Service update opportunities" ON opportunities FOR UPDATE USING (true);
CREATE POLICY "Service insert subcontractors" ON subcontractors FOR INSERT WITH CHECK (true);
CREATE POLICY "Service update subcontractors" ON subcontractors FOR UPDATE USING (true);
CREATE POLICY "Service insert bids" ON bids FOR INSERT WITH CHECK (true);
CREATE POLICY "Service update bids" ON bids FOR UPDATE USING (true);
CREATE POLICY "Service insert logs" ON scraping_logs FOR INSERT WITH CHECK (true);
CREATE POLICY "Service insert followups" ON followup_logs FOR INSERT WITH CHECK (true);
CREATE POLICY "Service insert performance" ON contracts FOR INSERT WITH CHECK (true);
CREATE POLICY "Service update performance" ON contract_performance FOR UPDATE USING (true);


-- 8. REALTIME (para el dashboard v0)
ALTER PUBLICATION supabase_realtime ADD TABLE opportunities;
ALTER PUBLICATION supabase_realtime ADD TABLE bids;
ALTER PUBLICATION supabase_realtime ADD TABLE contract_performance;
