EX_Cycles = {"ld": 2, "sd": 2, "subi": 2, "addi": 2, "fmul.d": 6, "fdiv.d": 12,"bne":5}


Instruction_queue = []
cur = 0
clock = 1


def push(Instruction_queue, instr):
    instr1 = instr.replace(',', ' ').replace('(', ' ').replace(')', ' ').split()

    instruction = Instruction(instr, instr1[0], instr1[2], instr1[3], instr1[1])
    Instruction_queue.append(instruction)


def pop():
    global cur
    if cur < len(Instruction_queue):
        instr = Instruction_queue[cur]
        cur += 1
        return instr
    else:
        return None


def success():
    global cur
    return cur >= len(Instruction_queue)


class Instruction:
    def __init__(self, instruction, op, j, k, dest, issue_time=None, exec_time=None, wirte_time=None, commit_time=None):
        self.instruction = instruction
        self.op = op
        self.vj = j
        self.vk = k
        self.dest = dest
        self.issue_time = issue_time
        self.exec_time = exec_time
        self.write_time = wirte_time
        self.commit_time = commit_time

    def __str__(self):
        return f"{self.instruction} "


class ReorderBufferEntry:

    def __init__(self, entry, busy="No", instruction=None, time=None, dest=None, value=None,flag=False):
        self.entry = entry
        self.busy = busy
        self.instruction = instruction
        self.time = time
        self.dest = dest
        self.value = value  # write result之后才有value 用来看冒险是否用的是最新的值
        self.flag= False

class ReservationStation:
    def __init__(self, name, busy="No", op=None, vj=None, vk=None, qj=None, qk=None, dest=None, need_time=None):
        self.type = name
        self.busy = busy
        self.op = op
        self.vj = vj
        self.vk = vk
        self.qj = qj
        self.qk = qk
        self.dest = dest
        self.need_time = need_time
        self.ready = 0
        self.entry = 0


class Registers:

    def __init__(self):
        self.entry = {f"x{i}": None for i in range(11)}
        self.busy = {f"x{i}": "No" for i in range(11)}


class Tomasulo:

    def __init__(self, Instruction_queue, output_path):
        self.reorderbufferentry = [ReorderBufferEntry(i) for i in range(1, 7)]
        self.reservationstation = [ReservationStation(name) for name in
                                   ["Load1", "Load2", "Add1", "Add2", "Add3", "Mult1", "Mult2","bne1","bne2"]]
        self.registers = Registers()
        self.instruction_queue = Instruction_queue
        self.rs_num = {"Load": 2, "Add": 3, "Mult": 2,"bne":2}
        self.commitorder = []
        self.output_path = output_path

    def Decode(self):
        # 把instruction_queue里的指令放入nullbuffer中
        nullbuffer = [buffer.entry for buffer in self.reorderbufferentry if buffer.busy == "No"]
        if not nullbuffer or success():
            return 0
        for i in range(2):
            if nullbuffer and not success():
                # put next instruction into ready entry in the entry buffer
                instr = pop()
                readyentry = nullbuffer[0] - 1
                nullbuffer.pop(0)  # 剩余buffer减一个
                self.reorderbufferentry[readyentry].busy = "Yes"
                self.reorderbufferentry[readyentry].instruction = instr
                self.reorderbufferentry[readyentry].time = "Decode"
                self.reorderbufferentry[readyentry].dest = instr.dest
                self.reorderbufferentry[readyentry].value = None
                self.commitorder.append(readyentry + 1)
        return 1

    def Issue(self):
        global clock
        for i in range(2):
            minentry = min((i for i, entry in enumerate(self.commitorder) if
                            self.reorderbufferentry[entry - 1].time == "Decode"), default=None)
        # 有需要issue的
            if minentry is not None:
                entry1 = self.reorderbufferentry[self.commitorder[minentry] - 1]
                instruction = entry1.instruction
                op = instruction.op
                instruction.issue_time = clock
                # if corresponding reservation station is available, issue the instruction

                if op =="bne":
                    entry1.time = "Issue"
                    if self.reservationstation[7].busy=="No":
                        index = 7
                    else:
                        index = 8
                    rs = self.reservationstation[index]
                    rs.entry = entry1.entry
                    rs.busy = "Yes"
                    rs.op = op
                    rs.vj = instruction.vj
                    rs.need_time = EX_Cycles[op]
                    rs.ready = 1  #先假设没有数据冒险
                    # if self.registers.busy[instruction.vj] == "No":
                    #     rs.vj = "Regs[" + instruction.vj + "]"
                    #     rs.qj = None
                    # else:
                    #     # use the new value of register
                    #     wait_entry = self.reorderbufferentry[self.registers.entry[instruction.vj] - 1].value
                    #     # if the new value has computed
                    #     if wait_entry is not None:
                    #         rs.vj = wait_entry
                    #         rs.qj = None
                    #     else:
                    #         # wait for the result
                    #         rs.vj = None
                    #         rs.qj = "#" + str(self.registers.entry[instruction.vj])
                    #         # the operand is not ready
                    #         rs.ready = 0



                if op in {"ld", "sd"} and self.rs_num["Load"] > 0:
                    self.rs_num["Load"] -= 1
                    entry1.time = "Issue"

                    # 具体存在哪个保留站

                    if self.reservationstation[0].busy == "No":
                        index = 0
                    else:
                        index = 1

                    rs = self.reservationstation[index]
                    rs.entry = entry1.entry
                    rs.busy = "Yes"
                    rs.op = op
                    rs.vj = instruction.vj
                    rs.need_time = EX_Cycles[op]

                    # ready indicates whether the rs is ready for execution
                    # (both first operand and second operand are ready)
                    rs.ready = 1

                    if op == "ld":
                        rs.vk = "Regs[" + instruction.vk + "]"
                        rs.dest = "#" + str(entry1.entry)  # 加载到寄存器需要等会 先记录该指令属于第几条指令

                        self.registers.entry[instruction.dest] = entry1.entry
                        self.registers.busy[instruction.dest] = "Yes"

                    elif op == "sd":
                        rs.vk = "Regs[" + instruction.vk + "]"
                        rs.dest = "Mem[" + str(instruction.vj) + "+" + str(rs.vk) + "]"
                        # if the original register value has not been changed
                        if self.registers.busy[instruction.dest] == "No":  # 说明这个寄存器目前无人使用
                            rs.vk = "Regs[" + instruction.dest + "]"
                            rs.qk = None
                        else:
                            # use the new value of register
                            wait_entry = self.reorderbufferentry[
                                self.registers.entry[instruction.dest] - 1].value  # 就是等待的最新值有没有更新
                            # if the new value has computed
                            if wait_entry is not None:
                                rs.vk = wait_entry
                                rs.qk = None
                            else:
                                # wait for the result
                                rs.vk = None
                                rs.qk = "#" + str(self.registers.entry[instruction.dest])
                                # the operand is not ready
                                rs.ready = 0
                # new instr issued,time change


            # # if corresponding reservation station is available, issue the instruction
                if op in {"addi", "subi"} and self.rs_num["Add"] > 0:
                    entry1.time = "Issue"
                    self.rs_num["Add"] -= 1

                    # the index of available reservation station
                    index = 2 if self.reservationstation[2].busy == "No" else 3
                    if index == 3 and not self.reservationstation[3].busy == "No":
                        index = 4

                    # update the states of the rs
                    rs = self.reservationstation[index]
                    rs.entry = entry1.entry
                    rs.busy = "Yes"
                    rs.op = op
                    rs.dest = "#" + str(entry1.entry)
                    rs.need_time = EX_Cycles[instruction.op]

                    # ready indicates whether the rs is ready for execution
                    # (both first operand and second operand are ready)
                    rs.ready = 1
                    # 加减乘除两个操作数都需要判断是否有冒险

                    if self.registers.busy[instruction.vj] == "No":
                        rs.vj = "Regs[" + instruction.vj + "]"
                        rs.qj = None
                    else:
                        # use the new value of register
                        wait_entry = self.reorderbufferentry[self.registers.entry[instruction.vj] - 1].value
                        # if the new value has computed
                        if wait_entry is not None:
                            rs.vj = wait_entry
                            rs.qj = None
                        else:
                            # wait for the result
                            rs.vj = None
                            rs.qj = "#" + str(self.registers.entry[instruction.vj])
                            # the operand is not ready
                            rs.ready = 0
                    rs.vk=instruction.vk
                    rs.qk = None
                    # # if the original register value has not been changed
                    # if self.registers.busy[instruction.vk] == "No":
                    #     rs.vk = "Regs[" + instruction.vk + "]"
                    #     rs.qk = None
                    # else:
                    #     # use the new value of register
                    #     wait_entry = self.reorderbufferentry[self.registers.entry[instruction.vk] - 1].value
                    #     # if the new value has computed
                    #     if wait_entry is not None:
                    #         rs.vk = self.reorderbufferentry[
                    #             self.registers.entry[instruction.vk] - 1].value
                    #         rs.qk = None
                    #     else:
                    #         # wait for the result
                    #         rs.vk = None
                    #         rs.qk = "#" + str(self.registers.entry[instruction.vk])
                    #         # the operand is not ready
                    #         rs.ready = 0

                    # update the time of registers correspondingly
                    self.registers.entry[instruction.dest] = entry1.entry
                    self.registers.busy[instruction.dest] = "Yes"

                # new instr issued,time change


            # if corresponding reservation station is available, issue the instruction
                if op in {"fmul.d", "fdiv.d"} and self.rs_num["Mult"] > 0:
                    entry1.time = "Issue"

                    self.rs_num["Mult"] -= 1

                    # the index of available reservation station
                    index = 5 if self.reservationstation[5].busy == "No" else 6

                    # update the states of the rs
                    rs = self.reservationstation[index]
                    rs.entry = entry1.entry
                    rs.busy = "Yes"
                    rs.op = instruction.op
                    rs.dest = "#" + str(entry1.entry)
                    rs.need_time = EX_Cycles[instruction.op]

                    # ready indicates whether the rs is ready for execution
                    # (both first operand and second operand are ready)
                    rs.ready = 1

                    # if the original register value has not been changed
                    if self.registers.busy[instruction.vj] == "No":
                        rs.vj = "Regs[" + instruction.vj + "]"
                        rs.qj = None
                    else:
                        # use the new value of register
                        wait_entry = self.reorderbufferentry[self.registers.entry[instruction.vj] - 1].value
                        # if the new value has computed
                        if wait_entry is not None:
                            rs.vj = self.reorderbufferentry[self.registers.entry[instruction.vj] - 1].value
                            rs.qj = None
                        else:
                            # wait for the result
                            rs.vj = None
                            rs.qj = "#" + str(self.registers.entry[instruction.vj])
                            # the operand is not ready
                            rs.ready = 0

                    # if the original register value has not been changed
                    if self.registers.busy[instruction.vk] == "No":
                        rs.vk = "Regs[" + instruction.vk + "]"
                        rs.qk = None
                    else:
                        # use the new value of register
                        wait_entry = self.reorderbufferentry[self.registers.entry[instruction.vk] - 1].value
                        # if the new value has computed
                        if wait_entry is not None:
                            rs.vk = self.reorderbufferentry[
                                self.registers.entry[instruction.vk] - 1].value
                            rs.qk = None
                        else:
                            # wait for the result
                            rs.vk = None
                            rs.qk = "#" + str(self.registers.entry[instruction.vk])
                            # the operand is not ready
                            rs.ready = 0

                    # 将对应目的寄存器的状态改为繁忙
                    self.registers.entry[instruction.dest] = entry1.entry
                    self.registers.busy[instruction.dest] = "Yes"

                    # new instr issued,time change

        return 0

    def Execute(self):
        global clock

        for rs in self.reservationstation:
            if rs.ready == 1 and rs.need_time >0:
                entry1 = rs.entry - 1
                if self.reorderbufferentry[entry1].time == "Issue":
                    # new instr begins Executing
                    self.reorderbufferentry[entry1].time = "Execute"  # 有些执行周期需要很长可以合并
                # execute one clock
                rs.need_time -= 1

                # finish executing, record the execution completion cycle.
                if rs.need_time == 0:
                    self.reorderbufferentry[entry1].instruction.exec_time = clock
                    self.reorderbufferentry[entry1].flag=True

        return 0

    def Write(self):
        global clock

        for i in range(2):
            minentry = min((entry for i, entry in enumerate(self.commitorder) if
                            self.reorderbufferentry[entry - 1].flag==True), default=None)
        # 有需要issue的
            if minentry is not None:

                for index, rs in enumerate(self.reservationstation):
                    if(rs.entry==minentry):
                # if the instr finishes exe, then write result
                        self.reorderbufferentry[rs.entry - 1].time = "Write result"
                        self.reorderbufferentry[rs.entry - 1].flag=False
                        # print(self.reorderbufferentry[rs.entry - 1].time)

                        self.reorderbufferentry[rs.entry - 1].instruction.write_time = clock

                        # use operands and op to compute result
                        result = None
                        if rs.op == "ld":
                            result = f"Mem[{rs.vj}+{rs.vk}]"
                        elif rs.op == "addi":
                            result = f"{rs.vj}+{rs.vk}"
                        elif rs.op == "subi":
                            result = f"{rs.vj}-{rs.vk}"
                        elif rs.op == "fmul.d":
                            result = f"{rs.vj}*{rs.vk}"
                        elif rs.op == "fdiv.d":
                            result = f"{rs.vj}/{rs.vk}"

                        # write the result into reorder buffer
                        if result is not None:
                            self.reorderbufferentry[rs.entry - 1].value = result

                        # if instr in reservation station is waiting the result, write the result to rs
                        for rs_temp in self.reservationstation:
                            flag = 0
                            if rs_temp.qj == f"#{rs.entry}":
                                rs_temp.qj = None
                                rs_temp.vj = result
                                flag = 1
                            if rs_temp.qk == f"#{rs.entry}":
                                rs_temp.qk = None
                                rs_temp.vk = result
                                flag = 1
                            # if two operands are ready, set ready=1
                            if flag and rs_temp.qk is None and rs_temp.qj is None:
                                rs_temp.ready = 1
                                rs_temp.need_time += 1

                        break

        return 0

    def Commit(self):
        global clock
        update = 0
        if clock==17:
            for instruction in self.commitorder:
                print(instruction)
        for i in range(len(self.reorderbufferentry)):
            rf = self.reorderbufferentry[i]
            if rf.time == "Commit":
                rf.busy, rf.instruction, rf.time, rf.dest, rf.value = "No", None, None, None, None

        # for instr that wrote result, commit in order
        for i in range(2):
            for i, rf in enumerate(self.reorderbufferentry):
                if len(self.commitorder) > 0 and i + 1 == self.commitorder[0] and rf.time == "Write result":
                    self.commitorder.pop(0)
                    rf.instruction.commit_time = clock
                    rf.time = "Commit"

                # release the resource from reservation station
                    rs = [rs for rs in self.reservationstation if rs.entry == i + 1][0]
                    rs.busy, rs.op, rs.vj, rs.vk, rs.qj, rs.qk, rs.dest = "No", None, None, None, None, None, None
                    rs.need_time = None
                    rs.ready = 0

                    if rs.type.startswith("Load"):
                        self.rs_num["Load"] += 1
                    elif rs.type.startswith("Add"):
                        self.rs_num["Add"] += 1
                    elif rs.type.startswith("Mult"):
                        self.rs_num["Mult"] += 1

                    # write result to register
                    if self.registers.entry[rf.dest] == i + 1:
                        self.registers.entry[rf.dest] = None
                        self.registers.busy[rf.dest] = "No"


        return update

    def writeprocess(self):
        global clock
        with open(self.output_path, 'a') as output_file:
            output_file.write(f"clock{clock} :\n")
            # write entry buffer
            output_file.write(f"reorderbuffer entry-----------------------------\n\n")
            for i, rb in enumerate(self.reorderbufferentry):
                if rb.time is not None:
                    output_file.write(
                        f"entry {i + 1}: {rb.busy}\t, {rb.instruction}\t, {rb.time} \t, {rb.dest} \t,{rb.value} \t \n")
                else:
                    output_file.write(f"entry{i + 1} : \t, \t, \t, \t, \t, \t, \t,\t \n")
            output_file.write(f"\n\n")
            output_file.write(f"reservation station-----------------------------\n\n")
            # write reservation station
            for i, rs in enumerate(self.reservationstation):
                output_file.write(f"{rs.type}\t: {rs.busy} , ")
                output_file.write(f"{rs.op}\t, " if rs.op is not None else "\t, ")
                output_file.write(f"{rs.vj}\t, " if rs.vj is not None else "\t, ")
                output_file.write(f"{rs.vk}\t, " if rs.vk is not None else "\t, ")
                output_file.write(f"{rs.qj}\t, " if rs.qj is not None else "\t, ")
                output_file.write(f"{rs.qk}\t, " if rs.qk is not None else "\t, ")
                output_file.write(f"{rs.dest}\t;\n" if rs.dest is not None else "\t;\n")
            output_file.write(f"\n\n")
            output_file.write(f"registers-----------------------------\n\n")
            # write register status
            entry1 = self.registers
            output_file.write("reorderbuffer_entry: x0:")
            output_file.write(f"{entry1.entry['x0']}   ; x1:" if entry1.entry["x0"] is not None else "   ; x1:")
            for i in range(1, 10):
                output_file.write(
                    f"{entry1.entry['x' + str(i)]}   ; x{i + 1}:" if entry1.entry[
                                                                         "x" + str(i)] is not None else "   ; x" + str(
                        i + 1) + ":")
            output_file.write(f"{entry1.entry['x10']}   ;\n" if entry1.entry["x10"] is not None else "   ;\n")

            busy = self.registers.busy
            output_file.write("Busy   : x0:")
            for i in range(0, 10):
                output_file.write(f"{busy['x' + str(i)]} ; x{i + 1}:")
            output_file.write(f"{busy['x10']} ;\n" if busy["x10"] is not None else ";\n")

            output_file.write("-----------------------------------------------------------------------------------\n\n")

    def write_results(self):
        with open(self.output_path, 'a',encoding='utf-8') as output_file:
            output_file.write(
                f"指令 \t , 发射指令的时钟周期\t, 执⾏指令的时钟周期 \t, 访问存储器的时钟周期\t, 写CDB的时钟周期\t\n"
            )
            for instr in self.instruction_queue:
                output_file.write(
                    f"{instr.instruction} \t: {instr.issue_time} \t, {instr.exec_time} \t, {instr.write_time} \t, {instr.commit_time}\n")
    def run(self):
        global clock
        while True:
            # run Tomasulo until all instr have been committed
            if all(rf.time is None for rf in self.reorderbufferentry) and success():
                break
            # record whether the time changes
            # update = 0
            # update =self.Decode()
            # update = update | self.Issue()
            # update = update | self.Execute()
            # update = update | self.Write()
            # update = self.Commit()
            update = 0
            update = update | self.Commit()
            update = update | self.Write()
            update = update | self.Execute()
            update = update | self.Issue()
            update = update | self.Decode()
            # if time changes, write new time to output_file

            self.writeprocess()
            # tick the clock
            clock += 1

        # write the execution cycles of instructions to output_file
        self.write_results()


if __name__ == '__main__':
    Tomasulo = Tomasulo(Instruction_queue, "output2.txt")

    # read input_file and initial the instruction queue in Tomasulo
    with open("2.txt", "r") as file:
        lines = [line.rstrip('\n') for line in file]
        for line in lines:
            push(Instruction_queue, line)
        for instruction in Instruction_queue:
            print(instruction)

    Tomasulo.run()