-- Sync new DICOM instances to VNA main server via REST API
--
-- Environment variables (set in docker-compose.yml / .env):
--   VNA_MAIN_SERVER_URL  - base URL of the VNA main server (default: http://main-server:8000)
--   VNA_API_KEY          - API key for authenticating with the VNA main server
--   DICOM_SERVER_USER    - Orthanc username (for internal Orthanc API calls)
--   DICOM_SERVER_PASSWORD - Orthanc password (for internal Orthanc API calls)

-- Configuration
local MAIN_SERVER_URL = os.getenv("VNA_MAIN_SERVER_URL") or "http://main-server:8000"
local VNA_API_KEY = os.getenv("VNA_API_KEY") or ""
local ORTHANC_USER = os.getenv("DICOM_SERVER_USER") or ""
local ORTHANC_PASSWORD = os.getenv("DICOM_SERVER_PASSWORD") or ""

local SYNC_ENDPOINT = "/api/v1/internal/sync/dicom"
local MAX_RETRIES = 3
local RETRY_DELAY_SECONDS = 2

-- Logging helpers
local function log_info(msg)
    orthanc.LogInfo("[sync_to_vna] " .. msg)
end

local function log_warning(msg)
    orthanc.LogWarning("[sync_to_vna] " .. msg)
end

local function log_error(msg)
    orthanc.LogError("[sync_to_vna] " .. msg)
end

-- HTTP POST with authentication and retry logic
local function http_post_with_retry(url, payload_json, max_retries, retry_delay)
    local headers = {
        ["Content-Type"] = "application/json",
        ["Authorization"] = "Bearer " .. VNA_API_KEY,
    }

    for attempt = 1, max_retries do
        local success, result = pcall(function()
            return HttpPost(url, payload_json, headers)
        end)

        if success then
            log_info("POST " .. url .. " succeeded (attempt " .. attempt .. ")")
            return true, result
        else
            log_warning("POST " .. url .. " failed (attempt " .. attempt .. "/" .. max_retries .. "): " .. tostring(result))
            if attempt < max_retries then
                -- Simple delay using a busy-wait (Orthanc Lua has no sleep)
                local wait_until = os.time() + retry_delay
                while os.time() < wait_until do end
            end
        end
    end

    return false, "All " .. max_retries .. " attempts failed"
end

-- Main callback: triggered when a stable study arrives in Orthanc
function OnStableInstance(modality, instanceId, tags, metadata)
    -- Skip structured reports and presentation states
    if modality == "SR" or modality == "PR" then
        log_info("Skipping modality: " .. modality .. " for instance: " .. instanceId)
        return
    end

    -- Extract DICOM tags with safe defaults
    local patient_id = tags["PatientID"] or ""
    local study_uid = tags["StudyInstanceUID"] or ""
    local series_uid = tags["SeriesInstanceUID"] or ""
    local study_description = tags["StudyDescription"] or ""
    local modality_tag = tags["Modality"] or modality or ""
    local study_date = tags["StudyDate"] or ""
    local accession_number = tags["AccessionNumber"] or ""
    local patient_name = tags["PatientName"] or ""

    -- Validate required fields
    if study_uid == "" then
        log_warning("Missing StudyInstanceUID for instance: " .. instanceId .. ", skipping sync")
        return
    end

    -- Build the sync event payload
    local study_orthanc_id = ""
    local study_lookup_ok, study_lookup_result = pcall(function()
        return RestApiGet("/instances/" .. instanceId)
    end)
    if study_lookup_ok then
        local parse_ok, instance_info = pcall(ParseJson, study_lookup_result)
        if parse_ok and type(instance_info) == "table" then
            study_orthanc_id = instance_info["ParentStudy"] or ""
        end
    end

    local payload = {
        event_type = "study_stable",
        resource_type = "study",
        orthanc_id = study_orthanc_id,
        patient_id = patient_id,
        patient_name = patient_name,
        study_uid = study_uid,
        study_description = study_description,
        modalities = {modality_tag},
        series_count = 0,
        instance_count = 1,
        timestamp = os.date("!%Y-%m-%dT%H:%M:%SZ"),
    }

    if study_orthanc_id == "" then
        log_warning("Could not resolve parent study Orthanc ID for instance: " .. instanceId .. ", skipping sync")
        return
    end

    local json_payload = WriteJson(payload)

    -- Post to VNA main server sync endpoint
    local url = MAIN_SERVER_URL .. SYNC_ENDPOINT
    log_info("Syncing instance " .. instanceId .. " (study: " .. study_uid .. ") to " .. url)

    local ok, err = http_post_with_retry(url, json_payload, MAX_RETRIES, RETRY_DELAY_SECONDS)

    if not ok then
        log_error("Failed to sync instance " .. instanceId .. " after " .. MAX_RETRIES .. " retries: " .. tostring(err))
    end
end
