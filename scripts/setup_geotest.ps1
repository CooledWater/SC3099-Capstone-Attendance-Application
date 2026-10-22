<#
.SYNOPSIS
  Re-runnable setup for the SC3099 geolocation test (courses GEO-T1..GEO-T5).

.DESCRIPTION
  Talks only to the backend REST API - no direct database access:
    - courses   : POST  /courses/          admin (prompted ONLY when a course is missing)
                  PUT   /courses/{id}      course instructor (fixes venue/radius drift on re-run)
    - enrolments: POST  /enrollments/bulk  course instructor, create_accounts=false
    - sessions  : POST  /sessions/         course instructor, so the instructor owns and can edit them
                  PATCH /sessions/{id}     owner, only while the session is still 'scheduled'
  Every safety check runs before the first write. Only the GEO-T* courses, the 10 listed
  students' enrolments in them, and the sessions named "GEO-Tn GPS test <date>" are touched.

  Modes:  (default) dry run - reads only and prints the plan
          -Apply        create/fix records, then verify and print a summary
          -ShowResults  read-only check-in report for the test sessions
  Logins add the backend's normal login audit rows in every mode.
  Passwords are read with Read-Host -AsSecureString, kept in memory only, never printed or saved.
  See scripts/GEOLOCATION-TESTING.md.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateRange(-90, 90)][double]$Latitude,
    [Parameter(Mandatory = $true)][ValidateRange(-180, 180)][double]$Longitude,
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$VenueName,
    # Singapore local time (UTC+08:00), format yyyy-MM-dd HH:mm
    [Parameter(Mandatory = $true)][string]$StartLocal,
    [Parameter(Mandatory = $true)][ValidateRange(5, 720)][int]$DurationMinutes,
    [string]$BaseUrl = 'http://localhost:8000',
    [string]$Semester = '2026-S1',
    [string]$InstructorEmail = 'instructor@gmail.com',
    [string]$AdminEmail = '',
    [switch]$Apply,
    [switch]$ShowResults
)

$ErrorActionPreference = 'Stop'
if ($Apply -and $ShowResults) { throw 'Use either -Apply or -ShowResults, not both' }
if ($Latitude -eq 0 -and $Longitude -eq 0) { throw 'Latitude/Longitude 0,0 is not a real venue - pass the measured coordinates' }

$Api = $BaseUrl.TrimEnd('/') + '/api/v1'
$Inv = [Globalization.CultureInfo]::InvariantCulture
$Sgt = [TimeSpan]::FromHours(8)

$Courses = @(
    @{ Code = 'GEO-T1'; Radius = 25 },
    @{ Code = 'GEO-T2'; Radius = 50 },
    @{ Code = 'GEO-T3'; Radius = 100 },
    @{ Code = 'GEO-T4'; Radius = 200 },
    @{ Code = 'GEO-T5'; Radius = 400 }
)
$Students = @('student1@gmail.com') + (2..10 | ForEach-Object { 'sc3099.geotest.student{0:D2}@example.com' -f $_ })
$Flags = [ordered]@{ require_liveness_check = $false; require_face_match = $false; require_motion_check = $false }

# ---------- helpers ----------
function Invoke-Api([string]$Method, [string]$Path, [string]$Token, $Body) {
    $params = @{ Method = $Method; Uri = $Api + $Path; ContentType = 'application/json'; UseBasicParsing = $true }
    if ($Token) { $params.Headers = @{ Authorization = "Bearer $Token" } }
    if ($null -ne $Body) { $params.Body = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 5 -Compress)) }
    try { return Invoke-RestMethod @params }
    catch {
        $code = 0
        if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
        # Only the server's error detail is shown - never the request body.
        throw "API $Method $Path failed (HTTP $code): $($_.ErrorDetails.Message)"
    }
}

function Connect-As([string]$Email, [string]$ExpectedRole) {
    $secure = Read-Host -AsSecureString "Password for $Email"
    $plain = (New-Object System.Management.Automation.PSCredential($Email, $secure)).GetNetworkCredential().Password
    try { $login = Invoke-Api 'POST' '/auth/login' $null @{ email = $Email; password = $plain } }
    finally { $plain = $null; $secure.Dispose() }
    if ($login.user.role -ne $ExpectedRole) { throw "$Email has role '$($login.user.role)', expected '$ExpectedRole'" }
    return @{ Token = $login.access_token; Id = $login.user.id }
}

function ConvertTo-Utc($Value) {
    # Backend datetimes are naive UTC.
    if ($Value -is [datetime]) { return New-Object DateTimeOffset([datetime]::SpecifyKind($Value, 'Utc')) }
    return [DateTimeOffset]::Parse([string]$Value, $Inv, [Globalization.DateTimeStyles]::AssumeUniversal)
}

function Format-Iso([DateTimeOffset]$Value) { $Value.ToString("yyyy-MM-dd'T'HH:mm:sszzz", $Inv) }
function Format-Sgt($Value) { (ConvertTo-Utc $Value).ToOffset($Sgt).ToString('yyyy-MM-dd HH:mm', $Inv) }

function Test-Differs($A, $B) {
    if ($null -eq $A -or $null -eq $B) { return -not ($null -eq $A -and $null -eq $B) }
    return [math]::Abs([double]$A - [double]$B) -gt 1e-9
}

function Get-AllCourses([string]$Active) {
    $items = @(); $offset = 0
    while ($true) {
        $page = Invoke-Api 'GET' "/courses/?is_active=$Active&limit=100&offset=$offset" $null $null
        $batch = @($page.items)
        $items += $batch; $offset += $batch.Count
        if ($batch.Count -eq 0 -or $offset -ge $page.total) { break }
    }
    return $items
}

function Get-TestSession([string]$CourseId, [string]$Name, [string]$Token) {
    $list = Invoke-Api 'GET' "/sessions/?course_id=$CourseId&limit=100" $Token $null
    return @($list.items | Where-Object { $_.name -eq $Name })
}

function Get-ExpectedStatus([double]$Distance, [double]$Radius) {
    # Mirrors main.py _assess_checkin_geofence with the default risk_threshold 0.5:
    # risk = min(d/r, 2)/2, so risk >= 0.5 exactly when d >= r.
    if ($Distance -gt 2 * $Radius) { return 'rejected' }
    if ($Distance -ge $Radius) { return 'flagged' }
    return 'approved'
}

# ---------- inputs ----------
try { $localStart = [datetime]::ParseExact($StartLocal, 'yyyy-MM-dd HH:mm', $Inv) }
catch { throw "StartLocal must look like '2026-10-23 14:00' (Singapore time)" }
$start = New-Object DateTimeOffset($localStart, $Sgt)
$end = $start.AddMinutes($DurationMinutes)
$sessionName = { param($code) "$code GPS test $($localStart.ToString('yyyy-MM-dd', $Inv))" }
$times = [ordered]@{
    scheduled_start = Format-Iso $start; scheduled_end = Format-Iso $end
    checkin_opens_at = Format-Iso $start; checkin_closes_at = Format-Iso $end
}

$mode = if ($Apply) { 'APPLY (will write)' } elseif ($ShowResults) { 'RESULTS (read only)' } else { 'DRY RUN (read only)' }
Write-Host "Mode        : $mode"
Write-Host "Backend     : $Api"
Write-Host "Venue       : $VenueName ($Latitude, $Longitude)"
Write-Host "Session     : $($start.ToString('yyyy-MM-dd HH:mm', $Inv)) -> $($end.ToString('yyyy-MM-dd HH:mm', $Inv)) SGT (check-in open for the whole session)"
Write-Host "Courses     : $(($Courses | ForEach-Object { "$($_.Code)=$($_.Radius)m" }) -join ', ')"
Write-Host "Students    : $($Students.Count)"
$null = Invoke-RestMethod -Uri ($BaseUrl.TrimEnd('/') + '/health') -UseBasicParsing

$instructor = Connect-As $InstructorEmail 'instructor'
Write-Host "Instructor  : $InstructorEmail ok"

$activeCourses = Get-AllCourses 'true'
$inactiveCourses = Get-AllCourses 'false'

# ---------- results mode ----------
if ($ShowResults) {
    foreach ($spec in $Courses) {
        $course = @($activeCourses | Where-Object { $_.code -eq $spec.Code })
        if ($course.Count -eq 0) { Write-Warning "$($spec.Code): course not found"; continue }
        $session = @(Get-TestSession $course[0].id (& $sessionName $spec.Code) $instructor.Token)
        if ($session.Count -ne 1) { Write-Warning "$($spec.Code): test session not found"; continue }
        $radius = [double]$session[0].geofence_radius_meters
        $rows = @(Invoke-Api 'GET' "/checkins/session/$($session[0].id)" $instructor.Token $null)
        Write-Host ("`n{0}  r={1}m  session {2}  status={3}  check-ins={4}" -f $spec.Code, $radius, $session[0].id, $session[0].status, $rows.Count)
        $rows | Sort-Object student_email | ForEach-Object {
            $distance = $_.distance_from_venue_meters
            $expected = if ($null -ne $distance) { Get-ExpectedStatus $distance $radius } else { '?' }
            [pscustomobject]@{
                Student    = $_.student_email
                At         = Format-Sgt $_.checked_in_at
                DistanceM  = $distance
                Status     = $_.status
                Expected   = $expected
                Match      = if ($_.status -eq $expected) { 'yes' } else { 'CHECK' }
                Risk       = $_.risk_score
                Factors    = (@($_.risk_factors) | ForEach-Object { $_.type }) -join ','
            }
        } | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
    }
    return
}

# ---------- plan (no writes) ----------
$plan = @()
foreach ($spec in $Courses) {
    $code = $spec.Code
    if ($inactiveCourses | Where-Object { $_.code -eq $code }) { throw "$code exists but is deactivated - nothing changed; reactivate it or choose another code" }
    $existing = @($activeCourses | Where-Object { $_.code -eq $code })
    $want = [ordered]@{
        venue_name = $VenueName; venue_latitude = $Latitude; venue_longitude = $Longitude
        geofence_radius_meters = [double]$spec.Radius
        require_face_recognition = $false; require_device_binding = $false
    }
    $item = @{ Spec = $spec; Want = $want; CourseId = $null; CourseChanges = $null; Missing = $Students; SessionAction = 'create'; Session = $null }

    if ($existing.Count -gt 0) {
        $course = $existing[0]
        if ($course.instructor_id -ne $instructor.Id) { throw "$code already exists and belongs to another instructor - nothing changed" }
        $item.CourseId = $course.id
        $changes = [ordered]@{}
        if ($course.venue_name -ne $VenueName) { $changes.venue_name = $VenueName }
        foreach ($key in 'venue_latitude', 'venue_longitude', 'geofence_radius_meters') {
            if (Test-Differs $course.$key $want[$key]) { $changes[$key] = $want[$key] }
        }
        foreach ($key in 'require_face_recognition', 'require_device_binding') {
            if ($course.$key -ne $false) { $changes[$key] = $false }
        }
        $item.CourseChanges = $changes

        $roster = Invoke-Api 'GET' "/enrollments/course/$($course.id)?is_active=true" $instructor.Token $null
        $enrolled = @($roster.students | ForEach-Object { $_.student_email.ToLower() })
        $item.Missing = @($Students | Where-Object { $enrolled -notcontains $_.ToLower() })

        $found = @(Get-TestSession $course.id (& $sessionName $code) $instructor.Token)
        if ($found.Count -gt 1) {
            $item.SessionAction = 'duplicate'
        } elseif ($found.Count -eq 1) {
            $s = $found[0]
            $item.Session = $s
            # Effective venue: the session's own value, else the course's (after any course fix above).
            $sessionDrift = ((ConvertTo-Utc $s.scheduled_start) -ne $start) -or ((ConvertTo-Utc $s.scheduled_end) -ne $end) -or
                ((ConvertTo-Utc $s.checkin_opens_at) -ne $start) -or ((ConvertTo-Utc $s.checkin_closes_at) -ne $end) -or
                $s.require_liveness_check -or $s.require_face_match -or $s.require_motion_check
            $venueDrift = (Test-Differs $s.venue_latitude $Latitude) -or (Test-Differs $s.venue_longitude $Longitude) -or
                (Test-Differs $s.geofence_radius_meters $spec.Radius)
            if (-not ($sessionDrift -or $venueDrift)) { $item.SessionAction = 'ok' }
            elseif ($s.status -ne 'scheduled' -or $s.instructor_id -ne $instructor.Id) { $item.SessionAction = 'locked' }
            else { $item.SessionAction = 'update' }
        }
    }
    if ($item.SessionAction -eq 'create' -and $start -le [DateTimeOffset]::UtcNow.AddMinutes(2)) {
        throw "$code : no test session yet and the start time is not in the future - nothing changed"
    }
    $plan += $item
}

Write-Host "`n[Plan]"
foreach ($item in $plan) {
    $code = $item.Spec.Code
    $courseText = if (-not $item.CourseId) { 'create (admin)' } elseif ($item.CourseChanges.Count) { "update $($item.CourseChanges.Keys -join ',')" } else { 'ok' }
    $sessionText = switch ($item.SessionAction) {
        'create' { 'create' } 'ok' { "ok ($($item.Session.status))" } 'update' { 'update times/flags/venue' }
        'locked' { "differs but $($item.Session.status) - left unchanged" } 'duplicate' { 'DUPLICATES - left unchanged' }
    }
    Write-Host ("  {0,-7} r={1,4}m  course: {2,-28} enrol: {3,2} missing  session: {4}" -f $code, $item.Spec.Radius, $courseText, $item.Missing.Count, $sessionText)
    if ($item.SessionAction -in 'locked', 'duplicate') { Write-Warning "$code session needs manual review" }
}

if (-not $Apply) { Write-Host "`nDry run complete - nothing changed. Re-run with -Apply to make these changes."; return }

# ---------- apply ----------
$admin = $null
foreach ($item in $plan) {
    $code = $item.Spec.Code
    if (-not $item.CourseId) {
        if (-not $admin) {
            if (-not $AdminEmail) { $AdminEmail = Read-Host 'Admin email (needed to create courses)' }
            $admin = Connect-As $AdminEmail 'admin'
        }
        $body = [ordered]@{ code = $code; name = "SC3099 GeoTest r$($item.Spec.Radius)m"; semester = $Semester; instructor_id = $instructor.Id }
        foreach ($key in $item.Want.Keys) { $body[$key] = $item.Want[$key] }
        $item.CourseId = (Invoke-Api 'POST' '/courses/' $admin.Token $body).id
        Write-Host "  $code course created"
    } elseif ($item.CourseChanges.Count) {
        $null = Invoke-Api 'PUT' "/courses/$($item.CourseId)" $instructor.Token $item.CourseChanges
        Write-Host "  $code course updated"
    }

    if ($item.Missing.Count) {
        $result = Invoke-Api 'POST' '/enrollments/bulk' $instructor.Token @{ course_id = $item.CourseId; student_emails = $item.Missing; create_accounts = $false }
        if ($result.not_found -gt 0) {
            $bad = ($result.details | Where-Object { $_.status -eq 'not_found' } | ForEach-Object { $_.email }) -join ', '
            throw "$code : not enrolled (missing or not an active student account): $bad"
        }
        Write-Host "  $code enrolled $($result.enrolled)"
    }

    $body = [ordered]@{}
    foreach ($key in $times.Keys) { $body[$key] = $times[$key] }
    foreach ($key in $Flags.Keys) { $body[$key] = $Flags[$key] }
    if ($item.SessionAction -eq 'create') {
        $body.course_id = $item.CourseId; $body.name = & $sessionName $code
        $body.session_type = 'lecture'; $body.description = 'SC3099 GPS-only geolocation test'
        $null = Invoke-Api 'POST' '/sessions/' $instructor.Token $body
        Write-Host "  $code session created"
    } elseif ($item.SessionAction -eq 'update') {
        $body.venue_name = $VenueName; $body.venue_latitude = $Latitude; $body.venue_longitude = $Longitude
        $body.geofence_radius_meters = [double]$item.Spec.Radius
        $null = Invoke-Api 'PATCH' "/sessions/$($item.Session.id)" $instructor.Token $body
        Write-Host "  $code session updated"
    }
}

# ---------- verify + summary ----------
$summary = foreach ($item in $plan) {
    $code = $item.Spec.Code; $radius = $item.Spec.Radius
    $course = Invoke-Api 'GET' "/courses/$($item.CourseId)" $instructor.Token $null
    $roster = Invoke-Api 'GET' "/enrollments/course/$($course.id)?is_active=true" $instructor.Token $null
    $enrolled = @($roster.students | ForEach-Object { $_.student_email.ToLower() })
    $enrolledCount = @($Students | Where-Object { $enrolled -contains $_.ToLower() }).Count
    $session = @(Get-TestSession $course.id (& $sessionName $code) $instructor.Token)
    $s = if ($session.Count -eq 1) { $session[0] } else { $null }
    $courseOk = $course.instructor_id -eq $instructor.Id -and -not (Test-Differs $course.geofence_radius_meters $radius) -and
        -not (Test-Differs $course.venue_latitude $Latitude) -and -not (Test-Differs $course.venue_longitude $Longitude)
    $sessionOk = $null -ne $s -and -not $s.require_liveness_check -and -not $s.require_face_match -and -not $s.require_motion_check -and
        -not (Test-Differs $s.venue_latitude $Latitude) -and -not (Test-Differs $s.venue_longitude $Longitude) -and
        -not (Test-Differs $s.geofence_radius_meters $radius) -and (ConvertTo-Utc $s.scheduled_start) -eq $start -and
        (ConvertTo-Utc $s.checkin_closes_at) -eq $end
    [pscustomobject]@{
        Course    = $code
        RadiusM   = $course.geofence_radius_meters
        Enrolled  = "$enrolledCount/$($Students.Count)"
        SessionId = if ($s) { $s.id } else { '-' }
        StartSGT  = if ($s) { Format-Sgt $s.scheduled_start } else { '-' }
        EndSGT    = if ($s) { Format-Sgt $s.checkin_closes_at } else { '-' }
        Status    = if ($s) { $s.status } else { 'missing' }
        Verified  = if ($courseOk -and $sessionOk -and $enrolledCount -eq $Students.Count) { 'PASS' } else { 'FAIL' }
    }
}
Write-Host "`n[Summary]"
$summary | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
if (@($summary | Where-Object { $_.Verified -ne 'PASS' }).Count) { throw 'Verification failed - see FAIL rows above' }
Write-Host "All 5 courses, $(5 * $Students.Count) enrolments and 5 GPS-only sessions verified."
