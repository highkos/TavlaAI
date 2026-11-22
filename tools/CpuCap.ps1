<#
.SYNOPSIS
	Runs a command inside a Windows Job Object with a hard CPU rate cap.

.DESCRIPTION
	The cap is enforced by the kernel (JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP),
	not by polling or by thread-count heuristics. It applies to the whole
	process tree: every child the command spawns inherits the job, so a
	multi-process job cannot escape the budget.

	The percentage is a share of the *total* processor capacity of the
	machine, which is what a hosting provider's fair-use policy means.
	On a 3 vCPU box, -Percent 20 gives about 0.7 vCPU.

	The child is created suspended, assigned to the job, and only then
	resumed. Without that ordering a fast child could spawn grandchildren
	before the assignment and they would run uncapped.

.PARAMETER Percent
	CPU budget as a percentage of total machine capacity (1..100).

	Windows overshoots the requested rate by roughly 14% at low values.
	Measured on a 3-vCPU host: 10% -> 11.7%, 20% -> 23.1%, 25% -> 28.4%,
	50% -> 55.9%, 100% -> 100%. Ask for 20 when the ceiling is 25.

.PARAMETER CommandLine
	Full command line to run, e.g. 'python.exe ml\train_v2.py --steps 100'.

.PARAMETER WorkingDirectory
	Working directory for the child. Defaults to the current directory.

.PARAMETER TimeoutSeconds
	0 (default) waits forever. Otherwise the job is killed after the timeout.

.PARAMETER LogPath
	When set, the child's stdout and stderr are appended to this file. Without
	it the child gets its own console and its output is not captured.

.EXAMPLE
	.\CpuCap.ps1 -Percent 25 -CommandLine 'python.exe -c "print(1)"'

.EXAMPLE
	.\CpuCap.ps1 -Percent 25 -CommandLine 'python.exe ml\train_v2.py' -LogPath C:\Temp\job.log

.NOTES
	Exit code is the child's exit code, or -2 on timeout.
#>
[CmdletBinding()]
param(
	[Parameter(Mandatory = $true)]
	[ValidateRange(1, 100)]
	[int]$Percent,

	[Parameter(Mandatory = $true)]
	[string]$CommandLine,

	[string]$WorkingDirectory = (Get-Location).Path,

	[int]$TimeoutSeconds = 0,

	[string]$LogPath = ''
)

$ErrorActionPreference = 'Stop'

if (-not ('CpuCap.Native' -as [type])) {
	Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace CpuCap
{
	// The native struct is 8 bytes: a DWORD followed by a union of
	// { CpuRate } / { Weight } / { MinRate, MaxRate }. Declaring the union
	// members sequentially would make the struct 16 bytes and
	// SetInformationJobObject would fail with ERROR_BAD_LENGTH (24).
	[StructLayout(LayoutKind.Explicit, Size = 8)]
	public struct JOBOBJECT_CPU_RATE_CONTROL_INFORMATION
	{
		[FieldOffset(0)] public uint ControlFlags;
		[FieldOffset(4)] public uint CpuRate;
		[FieldOffset(4)] public uint Weight;
		[FieldOffset(4)] public ushort MinRate;
		[FieldOffset(6)] public ushort MaxRate;
	}

	[StructLayout(LayoutKind.Sequential)]
	public struct IO_COUNTERS
	{
		public ulong ReadOperationCount;
		public ulong WriteOperationCount;
		public ulong OtherOperationCount;
		public ulong ReadTransferCount;
		public ulong WriteTransferCount;
		public ulong OtherTransferCount;
	}

	[StructLayout(LayoutKind.Sequential)]
	public struct JOBOBJECT_BASIC_LIMIT_INFORMATION
	{
		public long PerProcessUserTimeLimit;
		public long PerJobUserTimeLimit;
		public uint LimitFlags;
		public UIntPtr MinimumWorkingSetSize;
		public UIntPtr MaximumWorkingSetSize;
		public uint ActiveProcessLimit;
		public UIntPtr Affinity;
		public uint PriorityClass;
		public uint SchedulingClass;
	}

	[StructLayout(LayoutKind.Sequential)]
	public struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
	{
		public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
		public IO_COUNTERS IoInfo;
		public UIntPtr ProcessMemoryLimit;
		public UIntPtr JobMemoryLimit;
		public UIntPtr PeakProcessMemoryUsed;
		public UIntPtr PeakJobMemoryUsed;
	}

	[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
	public struct STARTUPINFO
	{
		public int cb;
		public string lpReserved;
		public string lpDesktop;
		public string lpTitle;
		public int dwX;
		public int dwY;
		public int dwXSize;
		public int dwYSize;
		public int dwXCountChars;
		public int dwYCountChars;
		public int dwFillAttribute;
		public int dwFlags;
		public short wShowWindow;
		public short cbReserved2;
		public IntPtr lpReserved2;
		public IntPtr hStdInput;
		public IntPtr hStdOutput;
		public IntPtr hStdError;
	}

	[StructLayout(LayoutKind.Sequential)]
	public struct PROCESS_INFORMATION
	{
		public IntPtr hProcess;
		public IntPtr hThread;
		public int dwProcessId;
		public int dwThreadId;
	}

	[StructLayout(LayoutKind.Sequential)]
	public struct SECURITY_ATTRIBUTES
	{
		public int nLength;
		public IntPtr lpSecurityDescriptor;
		public int bInheritHandle;
	}

	public static class Native
	{
		[DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
		public static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string lpName);

		[DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
		public static extern IntPtr CreateFile(
			string lpFileName, uint dwDesiredAccess, uint dwShareMode,
			ref SECURITY_ATTRIBUTES lpSecurityAttributes, uint dwCreationDisposition,
			uint dwFlagsAndAttributes, IntPtr hTemplateFile);

		[DllImport("kernel32.dll", SetLastError = true)]
		public static extern bool SetInformationJobObject(
			IntPtr hJob, int infoClass, IntPtr info, uint infoLength);

		[DllImport("kernel32.dll", SetLastError = true)]
		public static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

		[DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
		public static extern bool CreateProcess(
			string lpApplicationName, string lpCommandLine,
			IntPtr lpProcessAttributes, IntPtr lpThreadAttributes,
			bool bInheritHandles, uint dwCreationFlags, IntPtr lpEnvironment,
			string lpCurrentDirectory, ref STARTUPINFO si, out PROCESS_INFORMATION pi);

		[DllImport("kernel32.dll", SetLastError = true)]
		public static extern uint ResumeThread(IntPtr hThread);

		[DllImport("kernel32.dll", SetLastError = true)]
		public static extern uint WaitForSingleObject(IntPtr hHandle, uint dwMilliseconds);

		[DllImport("kernel32.dll", SetLastError = true)]
		public static extern bool GetExitCodeProcess(IntPtr hProcess, out uint lpExitCode);

		[DllImport("kernel32.dll", SetLastError = true)]
		public static extern bool CloseHandle(IntPtr hObject);

		public const int JobObjectCpuRateControlInformation = 15;
		public const int JobObjectExtendedLimitInformation = 9;
		public const uint JOB_OBJECT_CPU_RATE_CONTROL_ENABLE = 0x1;
		public const uint JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP = 0x4;
		public const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;
		public const uint CREATE_SUSPENDED = 0x00000004;
		public const uint CREATE_NEW_CONSOLE = 0x00000010;
		public const uint INFINITE = 0xFFFFFFFF;
		public const uint WAIT_TIMEOUT = 0x102;
		public const uint STARTF_USESTDHANDLES = 0x00000100;
		public const uint FILE_APPEND_DATA = 0x0004;
		public const uint FILE_SHARE_READ = 0x00000001;
		public const uint FILE_SHARE_WRITE = 0x00000002;
		public const uint OPEN_ALWAYS = 4;
		public const uint FILE_ATTRIBUTE_NORMAL = 0x80;
		public static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);

		public static int Run(int percent, string commandLine, string workingDir, int timeoutSeconds, string logPath)
		{
			IntPtr job = CreateJobObject(IntPtr.Zero, null);
			if (job == IntPtr.Zero)
				throw new Exception("CreateJobObject failed: " + Marshal.GetLastWin32Error());

			try
			{
				// Kill the whole tree if this launcher dies, so a crashed
				// dispatcher cannot leave an uncapped job on the host.
				var ext = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
				ext.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
				int extSize = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
				IntPtr extPtr = Marshal.AllocHGlobal(extSize);
				try
				{
					Marshal.StructureToPtr(ext, extPtr, false);
					if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation, extPtr, (uint)extSize))
						throw new Exception("SetInformationJobObject(extended) failed: " + Marshal.GetLastWin32Error());
				}
				finally { Marshal.FreeHGlobal(extPtr); }

				// CpuRate is in hundredths of a percent: 25% -> 2500.
				var rate = new JOBOBJECT_CPU_RATE_CONTROL_INFORMATION();
				rate.ControlFlags = JOB_OBJECT_CPU_RATE_CONTROL_ENABLE | JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP;
				rate.CpuRate = (uint)(percent * 100);
				int rateSize = Marshal.SizeOf(typeof(JOBOBJECT_CPU_RATE_CONTROL_INFORMATION));
				IntPtr ratePtr = Marshal.AllocHGlobal(rateSize);
				try
				{
					Marshal.StructureToPtr(rate, ratePtr, false);
					if (!SetInformationJobObject(job, JobObjectCpuRateControlInformation, ratePtr, (uint)rateSize))
						throw new Exception("SetInformationJobObject(cpu rate) failed: " + Marshal.GetLastWin32Error());
				}
				finally { Marshal.FreeHGlobal(ratePtr); }

				var si = new STARTUPINFO();
				si.cb = Marshal.SizeOf(typeof(STARTUPINFO));
				PROCESS_INFORMATION pi;

				IntPtr logHandle = IntPtr.Zero;
				bool inherit = false;
				uint flags = CREATE_SUSPENDED;
				if (!string.IsNullOrEmpty(logPath))
				{
					var sa = new SECURITY_ATTRIBUTES();
					sa.nLength = Marshal.SizeOf(typeof(SECURITY_ATTRIBUTES));
					sa.bInheritHandle = 1;
					logHandle = CreateFile(logPath, FILE_APPEND_DATA,
						FILE_SHARE_READ | FILE_SHARE_WRITE, ref sa, OPEN_ALWAYS,
						FILE_ATTRIBUTE_NORMAL, IntPtr.Zero);
					if (logHandle == INVALID_HANDLE_VALUE)
						throw new Exception("CreateFile(log) failed: " + Marshal.GetLastWin32Error());
					si.dwFlags = (int)STARTF_USESTDHANDLES;
					si.hStdOutput = logHandle;
					si.hStdError = logHandle;
					inherit = true;
				}
				else
				{
					flags |= CREATE_NEW_CONSOLE;
				}

				try
				{
					if (!CreateProcess(null, commandLine, IntPtr.Zero, IntPtr.Zero, inherit,
							flags, IntPtr.Zero, workingDir, ref si, out pi))
						throw new Exception("CreateProcess failed: " + Marshal.GetLastWin32Error());
				}
				finally
				{
					if (logHandle != IntPtr.Zero) CloseHandle(logHandle);
				}

				try
				{
					if (!AssignProcessToJobObject(job, pi.hProcess))
						throw new Exception("AssignProcessToJobObject failed: " + Marshal.GetLastWin32Error());

					ResumeThread(pi.hThread);

					uint waitMs = timeoutSeconds > 0 ? (uint)(timeoutSeconds * 1000) : INFINITE;
					uint wr = WaitForSingleObject(pi.hProcess, waitMs);
					uint code = 0;
					GetExitCodeProcess(pi.hProcess, out code);
					if (wr == WAIT_TIMEOUT) return -2;
					return (int)code;
				}
				finally
				{
					CloseHandle(pi.hThread);
					CloseHandle(pi.hProcess);
				}
			}
			finally
			{
				CloseHandle(job);
			}
		}
	}
}
'@
}

$code = [CpuCap.Native]::Run($Percent, $CommandLine, $WorkingDirectory, $TimeoutSeconds, $LogPath)
exit $code
