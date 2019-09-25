
See also:
- [My FE9 notes repository](https://github.com/StanHash/FE9-DOC).
- [Rubbish FE9 script dumper](https://github.com/StanHash/FE9-DOC/blob/master/Tools/Py/script_anal.py).

# FE9 event scripts doc/notes

As usual, I decided to not do the other things I was working and do something else again. This time, I felt like checking out FE9. Fun fact: FE9 has procs too, and they're better than GBAFE procs. It also has vtables and other C++ shenanigans. Also PowerPC is horrible and ARM is so much more reader friendly... but I digress. Here we're about them event scripts.

I usually don't post about my wip and/or smaller work but I felt like this would probably be interesting to some so this is kind of an exception. But be warned: This is fresh and wip.

## CMB files

They're all the CMB files inside the `Scripts` folder, somewhat unsurprisingly. As far as I'm aware, there's no other CMB files around.

It seems that `startup.cmb` is always loaded (it contains a number of callable utility scenes).

### file format / ScriptInfo struct layout

CMB files and ScriptInfo structs have effectively the same layout, but the way values are encoded differs (CMB files are little-endian with file offsets as pointers, ScriptInfo structs are big-endian (because PowerPC) with mapped addresses as pointers).

The function that loads CMB into memory is located at `FE9U:80013E24`. It is also responsible for converting it from little-endian to big-endian, and converting file offsets to real addresses.

	+00 | char[4] | "cmb\0"?
	+04 | char[4] | "Cxx\0"?
	+08 | char[4] | "cmb\0"?
	...
	+20 | short   | offset in some memory? (overwritten post-load)
	+22 | short   | size of some memory? (maybe globals)
	+24 | word    | offset/address of string pool
	+28 | word    | offset/address of SceneInfo address array

The rest of the file is reserved for the data that's referenced by `+24` and `+28`. Typically the string pool is located before the scene info address array, but technically they can be in any order.

### The string pool

The string pool is just that: a pool of (null-terminated) strings. It doesn't have any meaning on its own, but many instructions will refer to within it via offsets.

For example, if the string pool looks like this:

	00000000  4e 6f 72 6d 61 6c 4f 6e  6c 79 00 44 69 73 70 6f  |NormalOnly.Dispo|
	00000010  73 00 48 61 72 64 00 49  6e 73 74 61 6e 74 44 69  |s.Hard.InstantDi|
	00000020  73 70 6f 73 00 44 69 73  70 6f 73 46 69 72 73 74  |spos.DisposFirst|
	00000030  00 49 6e 73 74 61 6e 74  44 69 73 70 6f 73 46 69  |.InstantDisposFi|
	00000040  72 73 74 00 44 69 73 70  6f 73 43 6f 6e 74 69 6e  |rst.DisposContin|
	00000050  ...

An instruction could refer to the string `Hard` (which is the name of a function called via instruction `0x38`) via string pool offset `0x12`.

(Note: this string pool dump is from the startup.cmb script file, the string pool is located at `+2C` in that file)

### SceneInfo

First note: the data pointed to by `ScriptInfo+28` is an array *of addresses* (or offsets) to `SceneInfo`, not to `SceneInfo` directly. That array is also null-terminated.

	+00 | word     | address of a identifier string (may be 0)
	+04 | word     | address of script (function for Event functions)
	+08 | word     | address of parent ScriptInfo (0 for Event functions)
	+0C | byte     | kind
	+0D | byte     | argument count (for callable scenes)
	+0E | byte     | parameter count (for game events)
	+10 | short    | index (used for iteration)
	+12 | short    | variable count (including arguments!)
	+14 | short[?] | parameters

(Note: this same struct is also used for registering functions callable through events internally, which is what the `Event function` bits refer to).

Event kinds: (I haven't done much research into those yet)

| ID | PARAMETERS | DESCRIPTION
| -- | ---------- | --
| 0  | - | Callable?
| 3  | start turn, end turn, phase | Turn?
| 6  | start turn, end turn, phase | Also Turn?

## Scene scripts

FE9 scripts are *nothing* like GBAFE events. In fact, they're much more reminescent to the scripting from the one other set of GBA games I looked a bit at (Harvert Moon: (More) Friends of Mineral Town) ([see my notes for that if you're curious](https://github.com/StanHash/FOMT-DOC/blob/master/EventScripts.txt), [as well as my tentative decompiler for those](https://github.com/StanHash/mary)).

Scripts are simply a sequence of bytes. It reads them as follows: the first byte is the instruction id, and then it reads a fixed number of bytes depending on instruction to form the *operand*. If the operand is more than one byte large, they reprensnt the operand as a *big-endian* encoded number (as opposed to the ScriptInfo and SceneInfo fields in the CMB that are little-endian).

The script VM is stack-based, which means that almost all operations are done via pushing or popping from the stack. This is very powerful as it allows to easily chain any number of operations much more naturally than when using a register-based VM.

There is *only one* instruction that can be used to interface with the game state, and that is instruction `0x38` (`call.ext`, see below).

Speaking of instruction `0x38`/`call.ext`, this is also the only instruction to take *two* operands (the first 2 bytes refer to the name string while the last byte is the fallback paremeter count).

### Core instruction list

| ID   | MNEMONIC    | OPSIZE | DESCRIPTION
| ---- | ----------- | ------ | -----------
| `00` | `nop`       | 0      | does nothing
| `01` | `val.8`     | 1      | pushes variable value (operand is variable number)
| `02` | `val.16`    | 2      | ^
| `03` | `valx.8`    | 1      | pushes value from array (operand is array variable number, pops for index)
| `04` | `valx.16`   | 2      | ^
| `05` | `valy.8`    | 1      | pushes value from array (operand is variable of array pointer, pops for index)
| `06` | `valy.16`   | 2      | ^
| `07` | `ref.8`     | 1      | pushes variable address (operand is variable number)
| `08` | `ref.16`    | 2      | ^
| `09` | `refx.8`    | 1      | pushes indexed array address (operand is array variable number, pops for index)
| `0A` | `refx.16`   | 2      | ^
| `0B` | `refy.8`    | 1      | pushes indexed array address (operand is variable of array pointer, pops for index)
| `0C` | `refy.16`   | 2      | ^
| `0D` | `gval.8`    | 1      | same as `val.8` but for globals
| `0E` | `gval.16`   | 2      | same as `val.16` but for globals
| `0F` | `gvalx.8`   | 1      | same as `valx.8` but for globals
| `10` | `gvalx.16`  | 2      | same as `valx.16` but for globals
| `11` | `gvaly.8`   | 1      | same as `valy.8` but for globals
| `12` | `gvaly.16`  | 2      | same as `valy.16` but for globals
| `13` | `gref.8`    | 1      | same as `ref.8` but for globals
| `14` | `gref.16`   | 2      | same as `ref.16` but for globals
| `15` | `grefx.8`   | 1      | same as `refx.8` but for globals
| `16` | `grefx.16`  | 2      | same as `refx.16` but for globals
| `17` | `grefy.8`   | 1      | same as `refy.8` but for globals
| `18` | `grefy.16`  | 2      | same as `refy.16` but for globals
| `19` | `number.8`  | 1      | pushes operand
| `1A` | `number.16` | 2      | ^
| `1B` | `number.32` | 4      | ^
| `1C` | `string.8`  | 1      | pushes address of string (stringpool + operand)
| `1D` | `string.16` | 2      | ^
| `1E` | `string.32` | 4      | ^
| `1F` | `deref`     | 0      | pushes value pointed to address at top of stack, without popping
| `20` | `disc`      | 0      | naked pop (discards top of stack)
| `21` | `store`     | 0      | pops value, then address, stores value at address, pushes value
| `22` | `add`       | 0      | pops 2 values, pushes their sum
| `23` | `sub`       | 0      | pops 2 values, pushes their difference
| `24` | `mul`       | 0      | pops 2 values, pushes their product
| `25` | `div`       | 0      | pops 2 values, pushes their quotient
| `26` | `mod`       | 0      | pops 2 values, pushes their remainder
| `27` | `neg`       | 0      | pops 1 value, pushes its negative
| `28` | `mvn`       | 0      | pops 1 value, pushes its bitwise negation (aka flips bits)
| `29` | `not`       | 0      | pops 1 value, pushes its logical negation (zero becomes 1, non-zero becomes 0)
| `2A` | `orr`       | 0      | pops 2 values, pushes `A | B` (bitwise or)
| `2B` | `and`       | 0      | pops 2 values, pushes `A & B` (bitwise and)
| `2C` | `xor`       | 0      | pops 2 values, pushes `A ^ B` (bitwise exclusive or)
| `2D` | `lsl`       | 0      | pops 2 values, pushes `A << B` (bitwise left shift)
| `2E` | `lsr`       | 0      | pops 2 values, pushes `A >> B` (bitwise right shift)
| `2F` | `eq`        | 0      | pops 2 values, pushes 1 if `A == B` else 0
| `30` | `ne`        | 0      | pops 2 values, pushes 1 if `A != B` else 0
| `31` | `lt`        | 0      | pops 2 values, pushes 1 if `A < B` else 0 (unsure)
| `32` | `le`        | 0      | pops 2 values, pushes 1 if `A <= B` else 0
| `33` | `gt`        | 0      | pops 2 values, pushes 1 if `A > B` else 0 (unsure)
| `34` | `ge`        | 0      | pops 2 values, pushes 1 if `A >= B` else 0 (unsure)
| `35` | `eqstr`     | 0      | pops 2 string addresses, pushes 1 if strings are equal else 0
| `36` | `nestr`     | 0      | pops 2 string addresses, pushes 1 if strings are not equal else 0
| `37` | `call.loc`  | 1      | calls scene from the same script (operand is id)
| `38` | `call.ext`  | 2+1    | calls scene or function by name (first 2 byte operand refers to string (stringpool + operand), last byte is number of arguments
| `39` | `ret`       | 0      | returns from scene/ends scene (for callable scenes: topmost stack value is return value)
| `3A` | `b`         | 2      | branches to (pc + 1 + operand)
| `3B` | `by`        | 2      | pops value, branches to (pc + 1 + operand) if value is non-zero ("branch if yes")
| `3C` | `bky`       | 2      | pops value, pushes 1 and branches to (pc + 1 + operand) if value is non-zero ("branch and keep if yes")
| `3D` | `bn`        | 2      | pops value, branches to (pc + 1 + operand) if value is zero ("branch if no")
| `3E` | `bkn`       | 2      | pops value, pushes 1 and branches to (pc + 1 + operand) if value is zero ("branch and keep if no")
| `3F` | `yield`     | 0      | holds scene without ending it, giving control back to engine
| `40` | `<unknown>` | 4      | pops 4 bytes and do nothing (possibly dummied debug instruction)
| `41` | `printf`    | 1      | pops number, then pops that number of other values and calls printf (which is also dummied)

Note that all the mnemonics are just me making things up. If you are going to write a script dumper/editor feel free to change some (or all) of them if you feel like it is needed.

One could assume that all of the `mnem.xyz` opcodes are just generated differently by the script assembler depending on the operand. For this reason, I will omit the `.xyz` in examples later.

### Calling

Calling scenes and functions via the `call` instructions is done as follows:

1. Arguments are pushed onto the stack by the caller
2. Call
3. The return value is implicitely pushes onto the stack

When calling another scene: The arguments are popped from the stack and stored in the callee's local memory.

When calling a function: The arguments are popped from the stack and then passed to in order to the function.

### Scene scripts common patterns

#### Assignment of a variable

From `C00.cmb`:

	ref 0                # push address of variable #0
	string "PID_WAYU"    # push string "PID_WAYU" (callable argument)
	call UnitGetByPID, 1 # call UnitGetByPID
	store                # store result in variable #0 and keep result

Note that it is not uncommon for the game to do the above, which is to forget to user/discard the remaining value caused by the `store` instruction. It is unknown whether this was a bug or 

#### Short-circuiting logical and/or

This is what the `bky`/`bkn` instructions seem to be used for.

Logical and, from `startup.cmb`:

	  val 2
	  val 3
	  le
	  bkn L005E
	
	  val 2
	  val 4
	  le

	L005E:
	  bkn L0066
	  val 2
	  val 5
	  le

	L0066:
	  bn later

This was probably generated by a `if ([2] <= [3] && [2] <= [4] && [2] <= [5])`-like statement.

Logical or, from `startup.cmb`:

	  string "PID_JANAFF"
	  call UnitCheckLiveByPID
	  bky L0062

	  string "PID_VULCI"
	  call UnitCheckLiveByPID

	L0062:
	  bn later

Again, this was likely from a `if (UnitCheckLiveByPID("PID_JANAFF") || UnitCheckLiveByPID("PID_VULCI"))` statement.

## Event functions

Here's a big dump of all functions that are at some point registered as being callable via event scripts, with their mapped address, argument count and callable name.

<details>
<summary>Event Functions</summary>

	Address  a Name
	=======  = ====
	800BAD9C 2 Focus
	800BAE4C 2 InstantFocus
	800BAB64 1 UnitFocus
	800BACCC 0 FocusWait
	800BABFC 0 FocusHardWait
	800BAAD4 0 DefaultEscapeTalk
	800BA9BC 0 DefaultDieTalk
	800BA8F8 2 UnitEscape
	800BA784 0 AllUnitEscape
	800BA75C 3 SetTerrain
	800BA638 1 MindGetMoney
	800BA69C 2 _gi
	800BB0B4 1 global
	800BB080 1 regist
	800BB04C 1 get
	800BB018 1 set
	800BAFE4 1 clr
	800BAEAC 0 TalkExist
	800BAF1C 1 TalkEvent
	800BAEF8 0 TalkResume
	800BAF80 1 TalkEventDirect
	800BA5AC 1 RectBuild
	800BA528 1 RectLeave
	800BA4A8 1 RectKill
	800BA138 3 RectSetPos
	800B9B58 2 RectFadeIn
	800B9A9C 2 RectFadeOut
	800B9A34 2 RectFadeOutDelete
	800B9C14 5 RectMoveOffset
	800B9C38 6 RectMove
	800B99B8 2 GMapPenDraw1Seq
	800B98B8 1 GMapPenDrawWait
	800B983C 2 GMapPenReset
	800B97B8 2 GMapPenDispOnOff
	800B9724 3 GMapPenDarkOnOff
	800B9630 6 GMapPointOn
	800B95B4 2 GMapPointOff
	800B9548 1 GMapPointOffAll
	800B94CC 2 GMapRegionOn
	800B9450 2 GMapRegionOnSkipFlash
	800B93D4 2 GMapRegionOff
	800B9368 1 GMapRegionOffAll
	800B92EC 2 GMapRegionFlashOnce
	800B9258 3 GMapRegionFlashOnOff
	800B91AC 5 GMapFlagMarkOn
	800B9130 2 GMapFlagMarkOff
	800B90C4 1 GMapFlagMarkOffAll
	800BA438 2 RectGet
	800BA38C 3 RectSet
	800BA298 6 RectSetCurve
	80108FA8 1 RectPreLoad
	800BA230 2 RectAdjustBoundary
	8005BB2C 0 _pldone
	800B6E8C 5 intplGetValue
	800B9060 1 DialogDirect
	800B8FFC 1 Dialog
	8006F014 0 DialogResult
	8006F00C 1 DialogSetDefault
	800B8E5C 2 Dialog2Items
	800B8DE4 3 Dialog3Items
	800B8D54 4 Dialog4Items
	800B8D34 0 DialogGetRes
	800B8F98 1 DialogTutorial
	800B8ED0 1 td
	800B8EBC 0 tde
	800B8CB0 6 TimeiShow
	800B8C34 5 TimeiShowHold
	800B8BA8 7 TimeiShowGMap
	800B8B24 6 TimeiShowHoldGMap
	800B8AFC 2 TimeiShowHoldOff
	800B8AD8 1 TimeiShowHoldOffAll
	800B8A5C 5 TutShowKari
	800B8A28 2 Fade
	800B8A04 0 isFading
	800B8974 5 Flash
	800B88E8 0 FlashWait
	800B88C4 0 isFlash
	800B8894 1 WipeOut
	800B8864 1 WipeIn
	800B8840 0 WipeEnd
	800B87B4 0 WipeWait
	800B8790 0 isWipe
	800B874C 1 ProcKill
	800B870C 1 ProcExists
	800B861C 1 PadSetMask
	800B85EC 1 PadResetMask
	800B8534 0 NetuzoInit
	800B850C 3 NetuzoSet
	800B841C 3 NetuzoBattle
	800B8070 2 BGMPlay
	800B7FD8 3 BGMPlayVol
	800B7F98 3 BGMSetVol
	800B7EF8 1 BGMStop
	800B7E60 3 BGMFadeIn
	800B7DB4 2 BGMFadeOut
	800B7D08 2 BGMMute
	800B7C4C 2 BGMCont
	800B7C28 1 BGMQuietOn
	800B7C04 1 BGMQuietOff
	800B7A80 0 BGMResume
	800B7A2C 1 SFXPlay
	800B7A08 0 ENVQuietOn
	800B79E4 0 ENVQuietOff
	800B79B4 1 ENVSilentOn
	800B7990 0 ENVSilentOff
	800B796C 0 ENVNoisyOn
	800B7948 0 ENVNoisyOff
	800B7828 1 WaitF
	800B7790 1 WaitM
	800B83A4 6 AddTT
	800B8340 3 SetFragile
	800B82D8 4 SetShooter
	800B8298 2 SetPit
	800B8250 4 SetRock
	800B7938 0 GetRank
	800B790C 0 Normal
	800B78F0 0 Hard
	800B78D4 0 Maniac
	800B81C0 0 JyokyoMapCapture
	800B8198 0 JyokyoMapShow
	800B812C 0 JyokyoMapHide
	800B8174 0 JyokyoMapPlayerOn
	800B8150 0 JyokyoMapEnemyOn
	800B8108 0 JyokyoMapDelete
	800B76D0 1 MoviePlay
	800B7658 1 ChapterMoviePlay
	80089524 0 SetWhiteBackdrop
	800894F8 0 RemoveBackdrop
	800B7580 0 UnitsPush
	800B74AC 0 UnitsPush_Uninitialize
	800B7410 0 UnitsPop
	800B7378 0 UnitsPopWithoutMap
	800B7210 0 UnitsInitialize
	80110094 0 TTPMInit
	80110048 1 TTPMEntry
	800B72CC 0 AllPush
	800B727C 0 AllPop
	800C4384 0 ArenaDump
	800C0AF4 0 Comeback
	800C0AE0 0 DisableSkip
	800C0ACC 0 EnableSkip
	800B7200 0 Check
	800B719C 1 CheckAttackable
	800B7140 1 Join
	800B70EC 1 DispPreLoadWholeForce
	800B7098 1 DispLoadWholeForce
	800B7044 1 DispFreeWholeForce
	800B6DF0 0 SallyGetSurplus
	800B6DB8 2 SallySetByPos
	800B6D88 1 SallySetByGroup
	800B6D50 2 SallyAddByPos
	800B6D20 1 SallyAddByGroup
	800B6FE4 1 SelectAuxiliary
	800B6CD8 1 report
	800B6C6C 1 StaffRoll
	800B6C00 1 WarRecord
	800B6B94 1 IndividualWarRecord
	800B6B20 0 WaitPressAnyKey
	800B6AE4 1 MSEC2FRAME
	800B6AA8 1 FRAME2MSEC
	80016538 0 dump
	800B7250 0 UnitDispReload
	80023DC0 0 MapUpdate
	8014C6E0 0 _mf1
	8014C6B8 0 _mf2
	800B6F10 0 _intr
	800EB774 0 MCResult
	800C0750 0 SuspendEvent
	800C068C 0 ResumeEvent
	801E4540 0 TutorialResume
	800B6E00 1 Complete18
	800B6A70 0 BeginFinale
	800B6A38 0 EndFinale
	800B6A30 0 IsE3Version

	800BD610 1 ForceGetFirst
	800BD5E0 1 ForceGetCount
	800BD704 2 UnitGet
	800BD638 3 UnitSet
	800BD470 1 UnitGetNext
	800BD424 1 UnitGetForce
	800BD5AC 1 UnitGetByPID
	800BD4C0 2 UnitGetByPos
	800BD0CC 1 UnitGetX
	800BD08C 1 UnitGetY
	800BD034 1 UnitGetMaxHP
	800BCFF4 1 UnitGetHP
	800BCC88 1 UnitGetRace
	800BD3DC 1 UnitGetStatus
	800BD388 2 UnitClrStatus
	800BD334 2 UnitSetStatus
	800BCF9C 2 UnitSetHP
	800BCF44 2 UnitSetEXP
	800BCDF0 1 UnitForcedSally
	800BCD7C 1 UnitDontMoveSally
	800BCD58 0 MindGetMe
	800BCD34 0 MindGetTarget
	800BCD24 0 MindGetMind
	800BCC44 1 PIDisAlive
	800BCED4 2 UnitQueryPID
	800BCE64 2 UnitQueryJID
	800BCA38 2 UnitTransferToForce
	800BD284 1 UnitBreakup
	800BD1A4 2 UnitPairup
	800BD10C 1 UnitClassChange
	800BC9D4 2 UnitSetCpAttackSeq
	800BC970 2 UnitSetCpMoveSeq
	800BC90C 2 UnitSetCpHealSeq
	800BC8A8 2 UnitSetCpMTypeID
	800BC82C 2 UnitSearchItem
	800BC7C8 2 UnitAddItem
	800BC760 2 UnitDelItem
	800BC6E8 3 UnitReplaceItem
	800BC684 1 UnitGetWeaponCount
	800BC5FC 1 UnitGetItemCount
	800BC588 2 UnitQueryEquip
	800BC458 2 UnitSetEquip
	800BC4FC 2 UnitCanUseIt
	800BC3F4 1 UnitGetEquipWepI
	800BC380 1 UnitGetEquipAccI
	800BC29C 1 UnitSetWeaponAway
	800BC204 1 UnitSetAccAway
	800BC11C 2 UnitItemSetDrop
	800BC0A4 2 UnitItemGetValuation
	800BBFD0 1 UnitPutToWarehouse
	800BBFD0 1 UnitItemSendtoWarehouseAll
	800BBF04 2 UnitItemSendtoWarehouse
	800BCC34 1 BMSetTurn
	800BCC14 1 BMSetPhase
	800BCBBC 4 BMSetTanto
	800BCB80 1 BMSetMoney
	800BCB38 2 BMSetTerm
	800BCB0C 2 BMSetValue
	800BCAFC 0 BMGetChapter
	800BCC24 0 BMGetTurn
	800BCC04 0 BMGetPhase
	800BCB24 1 BMGetValue
	800BCB70 0 BMGetMoney
	800BCAEC 0 EventGetX
	800BCADC 0 EventGetY
	800BBD68 1 ItemGetIndex
	800BBE9C 2 UnitAddSkill
	800BBE1C 2 UnitTstSkill
	800BBD9C 2 UnitClrSkill
	8000CEE4 1 GetRnd
	800BBD44 2 MapGetUnit
	800BBD20 2 MapGetTerrain
	800BBCFC 2 MapGetSight
	800BBC58 2 UnitGetMoveCost
	800BBC50 0 GCST
	800BBC40 0 GetBattleType
	800BBC14 0 SysGetRound
	800BBB58 2 PersonGetYellLevel
	800BBA38 3 PersonSetYellLevel
	800BB9E8 1 CpClrNoMoveFlag
	800BB9E0 0 GetLanguage

	80127918 0 GameBind
	801278EC 0 GameUnbind
	80127BA8 1 TutorialCall
	80127B50 1 QueryLesson
	80127054 0 BeginMapHoldCursor
	80127028 0 EndMapHoldCursor
	801275BC 1 _pa
	80126FA0 1 _tt
	80126F7C 0 _tr
	80126944 0 Config_Tutorial
	8012690C 1 Config_TutSet_unitInfo
	801268D4 1 Config_TutSet_terInfo
	8012689C 1 Config_TutSet_otheridoshowing
	8012688C 1 Config_TutSet_XinfoPage
	8012687C 0 Config_TutGet_sfx_vol
	8012684C 1 Config_TutSet_sfx_vol
	80126830 0 GetTutorial
	80013E24 1 CmLoadScript
	80013D4C 0 CmFreeScript
	80013C78 1 CmSleepScript
	80013BD4 0 CmWakeupScripts
	80127A00 0 _seqini
	801279D4 0 _bmsini
	80126F58 1 ArcLoad
	80126F34 1 ArcFree
	80126EB0 2 _cmb_mess_load
	80126A60 0 TutorialInitialize
	80126D0C 0 TutorialSallyCreate
	80126CE8 0 TutorialSallyDelete
	80126CB4 0 TutorialBasesCreate
	80126C90 0 TutorialBasesDelete
	80126DE8 1 TutorialUnlock
	80126DB0 1 TutorialLock
	80126D78 1 TutorialLearn
	80126D40 1 TutorialForget
	80126E80 0 taikitk
	80126E50 0 turntk
	80126E20 0 turnatk
	80127000 1 TutShow
	8008F400 4 CreateNoticeFrame
	8008D9B8 7 CreateNoticeLFrame
	8008D988 0 DeleteNoticeFrame
	8012835C 3 Tut3SArrowUAnim
	801282E8 3 Tut3SArrowDAnim
	80128268 3 Tut3SArrowABAnim
	801281E4 3 Tut3SArrowBCAnim
	80128160 3 Tut3SArrowCAAnim

	8019D9BC 5 EventArrowAppend
	8019D958 2 EventArrowStart
	8019D8CC 2 EventArrowFocus
	8019D850 5 EventArrowColor
	8019D930 1 EventArrowFadeOut
	8019D7A8 0 EventArrowWait
	8019D90C 0 EventArrowDelete

	801A23D0 0 UnitFocusOff
	801A233C 0 UnitFocusOn
	801A21C0 0 UnitFadeIn
	801A212C 0 UnitFadeOut
	801A2098 0 UnitFadeOff
	801A1DB8 1 UnitWalkDir
	801A1D04 1 UnitWalkSlow
	801A1198 2 UnitMoveDir
	801A0F68 3 UnitMovePos
	801A0E84 3 UnitSetPos
	801A0D64 3 UnitRotate
	801A2464 0 UnitMoveWait
	801A0A10 2 UnitAnim
	801A0B20 3 UnitAnimF
	801A094C 1 UnitDead
	801A087C 1 UnitWarpOut
	801A06EC 3 UnitTackle
	801A0434 2 UnitTransform
	801A05F4 2 InstantUnitTransform
	801A147C 3 DisposGetGroupCenter
	801A19D8 1 Dispos
	801A1960 1 DisposAsynchronous
	801A1934 1 InstantDispos
	801A1884 1 InstantDisposRank
	801A17CC 1 DisposFirst
	801A17A0 1 InstantDisposFirst
	801A16E8 1 DisposContinue
	801A16BC 1 InstantDisposContinue
	801A1604 1 DisposWarp
	801A14D8 1 DisposAuxiliary
	801A0400 1 MapLoad
	801A0374 0 MapReload
	8019F7CC 2 InstantDoorOpen
	8019F688 2 InstantDoorClose
	8019F4A8 2 DoorOpen
	8019F2D0 2 DoorClose
	8019F13C 2 InstantRoofOpen
	8019F04C 2 InstantRoofClose
	8019EEE0 2 RoofOpen
	8019ED7C 2 RoofClose
	8019F230 2 TBoxOpen
	8019ED74 3 VisitIn
	8019ECB4 3 VisitOut
	8019EAF4 2 BuildDestruction
	801A0298 1 SetOutLink
	801A0258 2 SetSight
	801A01D8 1 SetWeather
	801A016C 3 SetAmbient
	801A0100 3 SetDiffuse
	801A0208 6 SetFog
	801A1BF4 1 SetGrid
	801A1B58 1 SetCircle
	801A1A90 1 SetSepia
	801A25FC 1 SetEventBattle
	801A0060 3 SetMapCamera
	8019FFBC 3 InstantSetMapCamera
	8019FF68 0 CopyMapCamera
	8019FEB8 0 PastMapCamera
	8019FE54 0 InstantPastMapCamera
	8019FE2C 0 CreateEventCamera
	8019FD40 4 SetEventCameraAt
	8019FCD0 4 SetEventCameraRot
	8019FCAC 1 StartEventCamera
	8019FC88 0 DeleteEventCamera
	8019FC08 0 EventCameraWait
	801A2004 1 SetEventCameraPrec
	8019EA74 2 ShowMapCursor
	8019EA48 0 HideMapCursor
	8019E818 3 EffectPlay
	8019E764 0 EffectWait
	8019E6D8 3 EventQuake
	8019E6B4 0 EventQuakeStop
	8019F9B4 2 BuildInstShow
	8019F914 2 BuildInstHide
	8019FA50 3 BuildInstAnim
	8019EC0C 3 SetRoofEnable
	801A1F38 2 GetMapHeightBase
	801A1E6C 2 GetMapHeight
	8019E690 1 SetPullCursor
	8019E668 1 SetCamSuspend
	8019E640 1 SetOnBtFocus
	8019E5D4 2 UnitSetFixed
	801A2254 1 UnitSetHold
	8019E564 1 HidePrim2D
	8019E528 0 GetFukiPosX
	8019E4EC 0 GetFukiPosY

	801B7818 2 AchieveSet
	801B7638 0 PlayerDeadCheck
	801B75F4 0 EnemyDeadCheck
	801B7564 1 EnemyUnitCheckByPID
	801B7488 0 EnemyMonkCheck
	801B73DC 0 EnemySelfDefenceCheck
	801B7330 0 EnemyTigerCheck
	801B7260 0 PlayerEscapeCheck
	801B7188 0 PlayerEscapeCount
	801B70C8 0 ShooterBulletCheck
	801B7094 0 GetDiedPlayerCount

</details>
