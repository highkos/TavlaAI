<#
.SYNOPSIS
	Queue worker for the remote training host.

.DESCRIPTION
	Polls a queue directory for ``*.job`` files, runs each one through
	``CpuCap.ps1`` so the whole process tree stays under a hard CPU-rate cap,
	and publishes the result as ``<name>.json`` in the done directory.

	The agent itself is idle between jobs, so it is not capped; every job it
	spawns is. Because a job is created with ``CREATE_SUSPENDED`` and assigned
	to its job object before it resumes, grandchildren cannot escape the cap.

	Job file (JSON):
		{
		  "name": "label-0001",
		  "commandLine": "python.exe ml\\gnubg_er.py ...",
		  "workingDirectory": "C:\\bgwork\\jobs\\label-0001",
		  "percent": 25,
		  "timeoutSeconds": 0
		}

	Result file (JSON):
		{
		  "name": "label-0001",
		  "exitCode": 0,
		  "startedAt": "...",
		  "finishedAt": "...",
		  "seconds": 12.3,
		  "log": "C:\\bgwork\\logs\\label-0001.log"
		}

.PARAMETER Root
	Agent root. Expects ``queue``, ``done``, ``logs`` and ``archive`` beneath it.

.PARAMETER PollSeconds
	Idle poll interval.

.PARAMETER DefaultPercent
	Cap used when a job file omits ``percent``. Defaults to 20 because the
	Windows CPU-rate control overshoots the requested value by roughly 14%:
	measured on a 3-vCPU host, 20% requested -> 23.1% actual, 25% -> 28.4%.
	Requesting 20% keeps the host under a 25% fair-use ceiling.

.EXAMPLE
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\bgwork\RemoteAgent.ps1
#>
[CmdletBinding()]
param(
	[string]$Root = 'C:\bgwork',
	[int]$PollSeconds = 5,
	[int]$DefaultPercent = 20
)

$ErrorActionPreference = 'Stop'

$queueDir   = Join-Path $Root 'queue'
$doneDir    = Join-Path $Root 'done'
$logDir     = Join-Path $Root 'logs'
$archiveDir = Join-Path $Root 'archive'
$capScript  = Join-Path $Root 'CpuCap.ps1'
$statusPath = Join-Path $Root 'agent.status'

foreach ($d in @($queueDir, $doneDir, $logDir, $archiveDir)) {
	if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

function Write-Status {
	param([string]$State, [string]$Job = '')
	$payload = [ordered]@{
		pid       = $PID
		state     = $State
		job       = $Job
		updatedAt = (Get-Date).ToString('o')
		host      = $env:COMPUTERNAME
	}
	$json = $payload | ConvertTo-Json -Compress
	try {
		[System.IO.File]::WriteAllText($statusPath, $json, (New-Object System.Text.UTF8Encoding($false)))
	} catch { }
}

function Invoke-Job {
	param([System.IO.FileInfo]$File, [string]$Name)

	$name = $Name
	$job = $null
	try {
		$job = Get-Content -LiteralPath $File.FullName -Raw | ConvertFrom-Json
	} catch {
		$err = [ordered]@{
			name       = $name
			exitCode   = -1
			error      = "bad job file: $($_.Exception.Message)"
			finishedAt = (Get-Date).ToString('o')
		}
		[System.IO.File]::WriteAllText((Join-Path $doneDir "$name.json"),
			($err | ConvertTo-Json -Compress), (New-Object System.Text.UTF8Encoding($false)))
		Move-Item -LiteralPath $File.FullName -Destination (Join-Path $archiveDir "$name.job") -Force
		return
	}

	$percent = if ($job.PSObject.Properties.Name -contains 'percent' -and $job.percent) { [int]$job.percent } else { $DefaultPercent }
	$wd      = if ($job.PSObject.Properties.Name -contains 'workingDirectory' -and $job.workingDirectory) { [string]$job.workingDirectory } else { $Root }
	$timeout = if ($job.PSObject.Properties.Name -contains 'timeoutSeconds') { [int]$job.timeoutSeconds } else { 0 }
	$logPath = Join-Path $logDir "$name.log"

	if (-not (Test-Path $wd)) { New-Item -ItemType Directory -Path $wd -Force | Out-Null }

	Write-Status -State 'running' -Job $name
	$started = Get-Date
	$sw = [System.Diagnostics.Stopwatch]::StartNew()

	$capArgs = @(
		'-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $capScript,
		'-Percent', $percent,
		'-CommandLine', [string]$job.commandLine,
		'-WorkingDirectory', $wd,
		'-LogPath', $logPath
	)
	if ($timeout -gt 0) { $capArgs += @('-TimeoutSeconds', $timeout) }

	# Optional per-job environment. The embeddable Python distribution ships a
	# ``._pth`` file, which makes CPython skip the usual ``sys.path[0]`` entry,
	# so multi-file Python jobs need PYTHONPATH pointing at the job directory.
	$savedEnv = @{}
	if ($job.PSObject.Properties.Name -contains 'env' -and $job.env) {
		foreach ($p in $job.env.PSObject.Properties) {
			$savedEnv[$p.Name] = [Environment]::GetEnvironmentVariable($p.Name, 'Process')
			[Environment]::SetEnvironmentVariable($p.Name, [string]$p.Value, 'Process')
		}
	}

	$code = -1
	try {
		& powershell.exe @capArgs
		$code = $LASTEXITCODE
	} catch {
		$code = -1
		try {
			Add-Content -LiteralPath $logPath -Value "agent: $($_.Exception.Message)"
		} catch { }
	}
	$sw.Stop()

	foreach ($k in $savedEnv.Keys) {
		[Environment]::SetEnvironmentVariable($k, $savedEnv[$k], 'Process')
	}

	$result = [ordered]@{
		name       = $name
		exitCode   = $code
		percent    = $percent
		startedAt  = $started.ToString('o')
		finishedAt = (Get-Date).ToString('o')
		seconds    = [math]::Round($sw.Elapsed.TotalSeconds, 2)
		log        = $logPath
	}
	[System.IO.File]::WriteAllText((Join-Path $doneDir "$name.json"),
		($result | ConvertTo-Json -Compress), (New-Object System.Text.UTF8Encoding($false)))
	Move-Item -LiteralPath $File.FullName -Destination (Join-Path $archiveDir "$name.job") -Force
	Write-Status -State 'idle'
}

Write-Status -State 'idle'

while ($true) {
	try {
		$jobs = @(Get-ChildItem -LiteralPath $queueDir -Filter '*.job' -File -ErrorAction SilentlyContinue |
				  Sort-Object LastWriteTime)
		if ($jobs.Count -eq 0) {
			Start-Sleep -Seconds $PollSeconds
			continue
		}
		foreach ($j in $jobs) {
			# Claim the file first so a second agent (or a restart) cannot
			# pick up the same job twice.
			$claimed = Join-Path $archiveDir ("{0}.{1}.claim" -f $j.BaseName, $PID)
			try {
				Move-Item -LiteralPath $j.FullName -Destination $claimed -Force
			} catch {
				continue
			}
			Invoke-Job -File (Get-Item -LiteralPath $claimed) -Name $j.BaseName
		}
	} catch {
		try {
			Add-Content -LiteralPath (Join-Path $logDir 'agent.log') -Value ("{0} {1}" -f (Get-Date).ToString('o'), $_.Exception.Message)
		} catch { }
		Start-Sleep -Seconds $PollSeconds
	}
}
