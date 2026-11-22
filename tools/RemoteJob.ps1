<#
.SYNOPSIS
	Submits a job to the remote training host and waits for the result.

.DESCRIPTION
	Copies the job's inputs to the remote work directory, drops a ``.job`` file
	into the agent queue, waits for the agent to publish ``<name>.json``, then
	pulls the log and any requested outputs back.

	The remote agent runs every job through ``CpuCap.ps1``, so the remote CPU
	never exceeds ``-Percent``. The default is 20 rather than 25 because the
	Windows CPU-rate control overshoots by roughly 14% (measured on a 3-vCPU
	host: 20% requested -> 23.1% actual, 25% -> 28.4%). Requesting 20% keeps
	the host under a 25% fair-use ceiling. The local machine is not capped:
	run local training directly, in parallel.

	Credentials are read from the environment, never from this file:
		TAVLAI_REMOTE_HOST   e.g. 192.227.177.143
		TAVLAI_REMOTE_USER   e.g. Administrator
		TAVLAI_REMOTE_PASS   password

.PARAMETER Name
	Unique job name. Used for the queue file, the log and the result.

.PARAMETER CommandLine
	Command to run on the remote, relative to the job directory.

.PARAMETER Upload
	Local files or directories copied into the remote job directory.

.PARAMETER Download
	Paths, relative to the remote job directory, copied back into -OutDir.

.PARAMETER OutDir
	Local directory for the log and downloaded outputs. Defaults to
	``ml/runs/remote/<Name>``.

.EXAMPLE
	$env:TAVLAI_REMOTE_HOST = '192.227.177.143'
	$env:TAVLAI_REMOTE_USER = 'Administrator'
	$env:TAVLAI_REMOTE_PASS = '...'
	.\tools\RemoteJob.ps1 -Name label-0001 `
		-CommandLine 'C:\bgwork\python\python.exe gnubg_er.py --in in.json --out out.json' `
		-Upload 'ml\artifacts\label_in.json' `
		-Download 'out.json'
#>
[CmdletBinding()]
param(
	[Parameter(Mandatory)][string]$Name,
	[Parameter(Mandatory)][string]$CommandLine,
	[int]$Percent = 20,
	[string[]]$Upload = @(),
	[string[]]$Download = @(),
	[string]$OutDir = '',
	[int]$TimeoutSeconds = 0,
	[int]$WaitSeconds = 0,
	[hashtable]$Env = @{},
	[string]$RemoteHost = $env:TAVLAI_REMOTE_HOST,
	[string]$RemoteUser = $env:TAVLAI_REMOTE_USER,
	[string]$RemotePass = $env:TAVLAI_REMOTE_PASS,
	[string]$RemoteRoot = 'C:\bgwork'
)

$ErrorActionPreference = 'Stop'

if (-not $RemoteHost) { throw 'RemoteHost is empty. Set TAVLAI_REMOTE_HOST or pass -RemoteHost.' }
if (-not $RemoteUser) { throw 'RemoteUser is empty. Set TAVLAI_REMOTE_USER or pass -RemoteUser.' }
if (-not $RemotePass) { throw 'RemotePass is empty. Set TAVLAI_REMOTE_PASS or pass -RemotePass.' }
if ($Percent -lt 1 -or $Percent -gt 100) { throw "Percent must be 1..100, got $Percent." }

$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $repoRoot "ml\runs\remote\$Name" }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$share = "\\$RemoteHost\C$"
$jobRel = "bgwork\jobs\$Name"
$jobDir = Join-Path $share $jobRel
$queueFile = Join-Path $share "bgwork\queue\$Name.job"
$doneFile = Join-Path $share "bgwork\done\$Name.json"
$logFile = Join-Path $share "bgwork\logs\$Name.log"

# --- connect ---------------------------------------------------------------
# net.exe writes to stderr for a missing connection; keep that non-fatal.
$ErrorActionPreference = 'Continue'
$null = & net.exe use $share /delete /y 2>&1
$useOut = & net.exe use $share "/user:$RemoteUser" $RemotePass 2>&1
$useCode = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($useCode -ne 0) { throw "net use failed: $useOut" }

try {
	# --- stage inputs ------------------------------------------------------
	if (Test-Path $jobDir) { Remove-Item -LiteralPath $jobDir -Recurse -Force }
	New-Item -ItemType Directory -Path $jobDir -Force | Out-Null

	foreach ($item in $Upload) {
		$src = if ([System.IO.Path]::IsPathRooted($item)) { $item } else { Join-Path $repoRoot $item }
		if (-not (Test-Path $src)) { throw "Upload not found: $src" }
		if (Test-Path $src -PathType Container) {
			# Copy the directory's contents, not the directory itself, so the
			# command line can use plain relative names.
			Copy-Item -Path (Join-Path $src '*') -Destination $jobDir -Recurse -Force
		} else {
			Copy-Item -LiteralPath $src -Destination $jobDir -Force
		}
	}

	# --- submit ------------------------------------------------------------
	Remove-Item -LiteralPath $doneFile -Force -ErrorAction SilentlyContinue
	Remove-Item -LiteralPath $logFile -Force -ErrorAction SilentlyContinue

	$job = [ordered]@{
		name             = $Name
		commandLine      = $CommandLine
		workingDirectory = "$RemoteRoot\jobs\$Name"
		percent          = $Percent
		timeoutSeconds   = $TimeoutSeconds
	}
	# The embeddable Python distribution ships a ``._pth`` file, which makes
	# CPython skip the usual ``sys.path[0]`` entry. Default PYTHONPATH to the
	# job directory so multi-file Python jobs can import their siblings.
	if ($Env.Count -eq 0) { $Env = @{ PYTHONPATH = "$RemoteRoot\jobs\$Name" } }
	$job['env'] = $Env

	$tmp = Join-Path $env:TEMP "$Name.job"
	[System.IO.File]::WriteAllText($tmp, ($job | ConvertTo-Json -Compress), (New-Object System.Text.UTF8Encoding($false)))
	Copy-Item -LiteralPath $tmp -Destination $queueFile -Force
	Remove-Item -LiteralPath $tmp -Force

	Write-Host "submitted '$Name' (cap ${Percent}%) -> $RemoteHost"

	# --- wait --------------------------------------------------------------
	$deadline = if ($WaitSeconds -gt 0) { (Get-Date).AddSeconds($WaitSeconds) } else { [datetime]::MaxValue }
	while (-not (Test-Path $doneFile)) {
		if ((Get-Date) -gt $deadline) { throw "timed out waiting for $doneFile" }
		Start-Sleep -Seconds 2
	}
	Start-Sleep -Milliseconds 300

	$result = Get-Content -LiteralPath $doneFile -Raw | ConvertFrom-Json
	Write-Host ("finished: exit={0} seconds={1}" -f $result.exitCode, $result.seconds)

	# --- collect -----------------------------------------------------------
	if (Test-Path $logFile) {
		Copy-Item -LiteralPath $logFile -Destination (Join-Path $OutDir "$Name.log") -Force
	}
	foreach ($rel in $Download) {
		$src = Join-Path $jobDir $rel
		if (-not (Test-Path $src)) { Write-Warning "download missing: $rel"; continue }
		$dest = Join-Path $OutDir (Split-Path -Leaf $rel)
		if (Test-Path $src -PathType Container) {
			Copy-Item -LiteralPath $src -Destination $dest -Recurse -Force
		} else {
			Copy-Item -LiteralPath $src -Destination $dest -Force
		}
	}
	[System.IO.File]::WriteAllText((Join-Path $OutDir 'result.json'),
		($result | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false)))

	Write-Host "outputs -> $OutDir"
	if ($result.exitCode -ne 0) { exit $result.exitCode }
}
finally {
	$ErrorActionPreference = 'Continue'
	$null = & net.exe use $share /delete /y 2>&1
}
