import os, sys

def read_int(input, byteCount, byteorder = 'little', signed = False):
	return int.from_bytes(input.read(byteCount), byteorder = byteorder, signed = signed)

def read_cstr(input):
	result = []

	while True:
		char = input.read(1)

		if char == b'\0':
			break

		result.append(char)

	return (b''.join(result)).decode('shift-jis')

SCR_OPCODES = {
	0x00: ("nop",    0), # nop

	# memory addressing
	# looks scary (it was for me), but most addressing opcodes seem unused/very rarely used (I have yet to see anything that isn't val or ref).
	0x01: ("val",    1), # [local + imm]
	0x02: ("val",    2), # [local + imm]
	0x03: ("valx",   1), # [local + num@0 + imm]
	0x04: ("valx",   2), # [local + num@0 + imm]
	0x05: ("valy",   1), # [num@0 + [local + imm]]
	0x06: ("valy",   2), # [num@0 + [local + imm]]
	0x07: ("ref",    1), # local + imm
	0x08: ("ref",    2), # local + imm
	0x09: ("refx",   1), # local + num@0 + imm
	0x0A: ("refx",   2), # local + num@0 + imm
	0x0B: ("refy",   1), # num@0 + [local + imm]
	0x0C: ("refy",   2), # num@0 + [local + imm]
	0x0D: ("gval",   1), # [global + imm]
	0x0E: ("gval",   2), # [global + imm]
	0x0F: ("gvalx",  1), # [global + num@0 + imm]
	0x10: ("gvalx",  2), # [global + num@0 + imm]
	0x11: ("gvaly",  1), # [num@0 + [global + imm]]
	0x12: ("gvaly",  2), # [num@0 + [global + imm]]
	0x13: ("gref",   1), # global + imm
	0x14: ("gref",   2), # global + imm
	0x15: ("grefx",  1), # global + num@0 + imm
	0x16: ("grefx",  2), # global + num@0 + imm
	0x17: ("grefy",  1), # num@0 + [global + imm]
	0x18: ("grefy",  2), # num@0 + [global + imm]

	# constants
	0x19: ("number", 1), # imm
	0x1A: ("number", 2), # imm
	0x1B: ("number", 4), # imm
	0x1C: ("string", 1), # string(imm)
	0x1D: ("string", 2), # string(imm)
	0x1E: ("string", 4), # string(imm)

	# operations
	0x1F: ("deref",  0), # push [addr@0]
	0x20: ("disc",   0), # naked pop
	0x21: ("store",  0), # [addr@1] = num@0
	0x22: ("add",    0), # (num@1 + num@0)
	0x23: ("sub",    0), # (num@1 - num@0)
	0x24: ("mul",    0), # (num@1 * num@0)
	0x25: ("div",    0), # (num@1 / num@0)
	0x26: ("mod",    0), # (num@1 % num@0)
	0x27: ("neg",    0), # -num@0
	0x28: ("mvn",    0), # ~num@0
	0x29: ("not",    0), # !num@0
	0x2A: ("orr",    0), # (num@1 | num@0)
	0x2B: ("and",    0), # (num@1 & num@0)
	0x2C: ("xor",    0), # (num@1 ^ num@0)
	0x2D: ("lsl",    0), # (num@1 << num@0)
	0x2E: ("lsr",    0), # (num@1 >> num@0)
	0x2F: ("eq",     0), # (num@1 == num@0)
	0x30: ("ne",     0), # (num@1 != num@0)
	0x31: ("lt?",    0), # unsure
	0x32: ("le",     0), # unsure
	0x33: ("gt?",    0), # unsure
	0x34: ("ge?",    0), # unsure
	0x35: ("eqstr",  0), # (str@1 == str@0)
	0x36: ("nestr",  0), # (str@1 != str@0)

	# jumps and calls
	0x37: ("call",   1), # call event by id
	0x38: ("call",   3), # call named
	0x39: ("ret",    0), # pops and return (end)
	0x3A: ("b",      2), # branch
	0x3B: ("by",     2), # branch if true
	0x3C: ("bky",    2), # branch and keep if true
	0x3D: ("bn",     2), # branch if false
	0x3E: ("bkn",    2), # branch and keep if false
	0x3F: ("yield",  0), # yield

	# debug (dummied)
	0x40: ("unkdbg", 4), # no-op (dummied)
	0x41: ("printf", 1), # calls printf (which is dummied) (FE10: no-op (dummied))

	# FE10 only
	0x42: ("inc",    0), # pops addr and increments word at addr
	0x43: ("dec",    0), # pops addr and decrements word at addr
	0x44: ("dup",    0), # pushes topmost stack value (effectively duplicating it)
	0x45: ("retn",   0), # return no, equivalent to (number 0, ret)
	0x46: ("rety",   0), # return yes, equivalent to (number 1, ret)
	0x47: ("assign", 0), # [addr@1] = num@0; equivalent to (store, disc)

}

def kind_str(kind, params):
	if kind == 0:
		return 'FUNC'

	if kind == 3:
		return 'TURN<{}>'.format(', '.join(str(i) for i in params))

	if len(params) > 0:
		return 'KIND{}<{}>'.format(kind, ', '.join(str(i) for i in params))

	return 'KIND{}'.format(kind)

def main(args):
	try:
		filename = args[0]

	except IndexError:
		sys.exit("Usage: {} <File>".format(sys.argv[0]))

	with open(filename, 'rb') as f:
		f.seek(0x24)

		strpool = read_int(f, 4)
		f.seek(read_int(f, 4))

		offEvents = []

		while True:
			off = read_int(f, 4)

			if off == 0:
				break

			offEvents.append(off)
			
		def next_int(here, ints):
			for i in ints:
				if i > here:
					return i

			return 99999999

		for num in range(len(offEvents)):
			offEvent = offEvents[num]

			f.seek(offEvent)

			offName = read_int(f, 4)
			offScr  = read_int(f, 4)
			read_int(f, 4) # reserved space
			kind = read_int(f, 1)
			argcnt = read_int(f, 1)
			paramcnt = read_int(f, 1)
			read_int(f, 2) # index (should be same as num)
			varcnt = read_int(f, 2)

			params = []

			f.seek(offEvent + 0x14)
			for i in range(paramcnt):
				params.append(read_int(f, 2))

			if offName != 0:
				f.seek(offName)
				name = read_cstr(f)

			else:
				name = 'unk_{}'.format(num)

			print('{} {}({}) {}// id:{} off:{:X}'.format(
				kind_str(kind, params),
				name,
				', '.join('arg_{}'.format(i) for i in range(argcnt)),
				'global ' if offName != 0 else '',
				num,
				offEvent))

			n = next_int(offEvent, offEvents)

			if offScr < n:
				f.seek(offScr)
				scrbytes = f.read(n - offScr)

				i = 0
				nextlim = 0

				while i < len(scrbytes):
					locoff = i

					op = scrbytes[i]
					i = i + 1

					if not op in SCR_OPCODES:
						print("  unknown opcode: {:02X}".format(op))
						continue

					if op == 0x38:
						# call special case

						stroff = (scrbytes[i] << 8) + scrbytes[i+1]
						i = i + 2

						callargs = scrbytes[i]
						i = i + 1

						f.seek(strpool + stroff)
						name = read_cstr(f)

						print('  L{:04X}:  call {}, {}'.format(locoff, name, callargs))

						continue

					opcode = SCR_OPCODES[op]

					if opcode[1] > 0:
						operand = 0

						for j in range(opcode[1]):
							operand = (operand << 8) + scrbytes[i]
							i = i + 1

						if op == 0x37:
							# call local special case
							# FE10 only behavior

							if (operand & 0x80) != 0:
								operand = ((operand << 8) & 0x7F) + scrbytes[i]
								i = i + 1

						if op >= 0x1C and op <= 0x1E:
							# string special case

							f.seek(strpool + operand)
							operand = "\"{}\"".format(read_cstr(f))

						if op >= 0x01 and op <= 0x0C:
							# local variable reference special case
							
							if operand < argcnt:
								operand = "arg_{}".format(operand)

							elif operand < varcnt:
								operand = "var_{}".format(operand - argcnt)

							else:
								operand = "bad_{}".format(operand - varcnt)

						if op >= 0x3A and op <= 0x3E:
							if operand & 1 << (((opcode[1]*8)) - 1):
								operand = -(((~operand)+1) & 0x7FFF);

							operand = i + operand - 2

							# branch special case
							nextlim = max([nextlim, operand])

							operand = 'L{:04X}'.format(operand)

						print("  L{:04X}:  {} {}".format(locoff, opcode[0], operand))

					else:
						print("  L{:04X}:  {}".format(locoff, opcode[0]))

					if op == 0x39 or op == 0x45 or op == 0x46:
						# ret/retn/rety special case

						if i > nextlim:
							break



if __name__ == '__main__':
	main(sys.argv[1:])
