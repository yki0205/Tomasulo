EX_Cycles = {"fld": 2, "fsd": 2,"fsub.d": 2, "fadd.d": 2, "fmul.d": 6, "fdiv.d": 12}


Instruction_queue = []
cur = 0
clock=1
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
        self.instruction = instruction  #存放一下完整的指令 没有被split过的
        self.op = op  #指令的操作类型
        self.vj = j  #指令的操作数a
        self.vk = k #指令的操作数b
        self.dest = dest  #指令的目的寄存器
        self.issue_time = issue_time#这些time是所处于这个阶段时当前的时钟周期数
        self.exec_time = exec_time
        self.write_time = wirte_time
        self.commit_time = commit_time
    def __str__(self):
        return f"{self.instruction} "
class ReorderBufferEntry:

     def __init__(self, entry, busy="No", instruction=None, time=None, dest=None, value=None):
        self.entry = entry #标识在ReorderBuffer中的第几条
        self.busy = busy    #缓冲区条目是否被占用
        self.instruction = instruction  #存的指令
        self.time = time  #time记录所处的是哪个阶段 如Issue Decode等等
        self.dest = dest#dest是目的寄存器 为防止冲突
        self.value = value#write result之后才有value 用来看冒险是否用的是最新的值
class ReservationStation:
    def __init__(self, name, busy="No", op=None, vj=None, vk=None, qj=None, qk=None, dest=None, need_time=None):
        self.type = name
        # type 即什么类型的保留站 这里load和mult定义了两个条目  add定义了三个条目
        self.busy = busy  # 保留站是否被占用
        self.op = op
        self.vj = vj  # 源操作数
        self.vk = vk
        self.qj = qj  # 源操作数是否需要等待其他指令的执行结果 即是否发生了数据冒险 None就是没有发生
        self.qk = qk
        self.dest = dest
        self.need_time = need_time  # 这个操作执行execute阶段所需要的时间周期数 在最开始以字典形式全局定义了
        self.ready = 0  # 保留站的这条指令是否准备好执行 1表示准备好
        self.entry = 0  # 存放的是reoderbuffer中的第几个条目
class Registers:

    def __init__(self):
        self.entry = {f"f{i}": None for i in range(11)}#这里的entry是在reorderbuffer中第几个条目
        self.busy = {f"f{i}": "No" for i in range(11)}

class Tomasulo:

    def __init__(self,Instruction_queue, output_path):
        self.reorderbufferentry = [ReorderBufferEntry(i) for i in range(1, 7)]#定义了7个条目大小作为缓冲区大小
        self.reservationstation = [ReservationStation(name) for name in
                                     ["Load1", "Load2", "Add1", "Add2", "Add3", "Mult1", "Mult2"]]#每个指令类型都有相应的reservation数量
        self.registers = Registers()#11个寄存器
        self.instruction_queue = Instruction_queue#存放指令的FIFO队列
        self.rs_num = {"Load": 2, "Add": 3, "Mult": 2}#记录每种指令空闲的保留站数目
        self.commitorder=[]#记录程序的指令顺序 以便按顺序commmit
        self.output_path = output_path#输出文件
    def Decode(self):
        #把instruction_queue里的指令放入nullbuffer中,nullbuffer就是reorderbuffer中没有被占用的条目
        nullbuffer=[buffer.entry for buffer in self.reorderbufferentry if buffer.busy == "No"]
        if not nullbuffer or success():
            return 0
        if nullbuffer and not success():
            # put next instruction into ready entry in the entry buffer
            instr = pop() #reorderbuffer有空位就可以pop一条指令出来
            readyentry = nullbuffer[0] - 1
            nullbuffer.pop(0)#剩余buffer减一个
            self.reorderbufferentry[readyentry].busy = "Yes"
            self.reorderbufferentry[readyentry].instruction = instr
            self.reorderbufferentry[readyentry].time = "Decode"
            self.reorderbufferentry[readyentry].dest = instr.dest
            self.reorderbufferentry[readyentry].value = None
            self.commitorder.append(readyentry+1)#commitorder就是按照reorderbuffer里的顺序
            return 1
    '''
    首先按commitorder顺序看reorderbuffer中有哪些指令是①属于decode阶段且②有对应的保留站条目空闲可用才可以进行到issue阶段

    其次分为了操作码为存取数（fsd fld) 加减法(fadd.d  fsub.d) 乘除法(fmul.d fdiv.d)三种情况讨论
    这里fsd / fld的情况要讨论数据冒险,因为源操作数是寄存器，要看这个寄存器当前是否处于busy状态来判断是否发生数据冒险
    而加减乘除两个操作数都需要判断是否有冒险

    最后记得在issue阶段就要把指令的目的寄存器的状态改为busy
    '''
    def Issue(self):
        global clock#需要定义一个全局的时钟 来跟踪每个阶段所处的是第几个时钟周期
        minentry = min((i for i, entry in enumerate(self.commitorder) if
                         self.reorderbufferentry[entry - 1].time == "Decode"), default=None)
        #有需要issue的
        if minentry is not None:
            entry1 = self.reorderbufferentry[self.commitorder[minentry] - 1]
            instruction = entry1.instruction
            op = instruction.op
            instruction.issue_time = clock#issue的时间就是当前时钟
            if op in {"fld", "fsd"} and self.rs_num["Load"] > 0:
                self.rs_num["Load"] -= 1 #reservation可用条目-1
                entry1.time = "Issue"

                #具体存在哪个保留站
                if self.reservationstation[0].busy == "No":
                   index = 0 
                else:
                    index =1

                rs = self.reservationstation[index]
                rs.entry = entry1.entry
                rs.busy = "Yes"
                rs.op = op
                rs.vj = instruction.vj
                rs.need_time = EX_Cycles[op]
                rs.ready = 1

                if op == "fld":
                    rs.vk = "Regs[" + instruction.vk + "]"
                    rs.dest = "#" + str(entry1.entry)#存数到寄存器需要等会 先记录该指令属于第几条指令

                    self.registers.entry[instruction.dest] = entry1.entry
                    self.registers.busy[instruction.dest] = "Yes"

                elif op == "fsd":
                    rs.vk = "Regs[" + instruction.vk + "]"
                    rs.dest = "Mem[" + str(instruction.vj) + "+" + str(rs.vk) + "]"

                    if self.registers.busy[instruction.dest] == "No":#说明这个寄存器目前无人使用 没发生数据冒险 就不需要等其他指令的执行结果了
                        rs.vk = "Regs[" + instruction.dest + "]"
                        rs.qk = None
                    else:

                        wait_entry = self.reorderbufferentry[self.registers.entry[instruction.dest] - 1].value#就是等待的最新值有没有更新

                        if wait_entry is not None:
                            rs.vk = wait_entry
                            rs.qk = None
                        else:

                            rs.vk = None
                            rs.qk = "#" + str(self.registers.entry[instruction.dest])

                            rs.ready= 0

                return 1


            if op in {"fadd.d", "fsub.d"} and self.rs_num["Add"] > 0:
                entry1.time = "Issue"
                self.rs_num["Add"] -= 1


                index = 2 if self.reservationstation[2].busy == "No" else 3
                if index == 3 and not self.reservationstation[3].busy == "No":
                    index = 4


                rs = self.reservationstation[index]
                rs.entry = entry1.entry
                rs.busy = "Yes"
                rs.op = op
                rs.dest = "#" + str(entry1.entry)
                rs.need_time = EX_Cycles[instruction.op]
                rs.ready = 1

#加减乘除两个操作数都需要判断是否有冒险

                if self.registers.busy[instruction.vj] == "No":
                    rs.vj = "Regs[" + instruction.vj + "]"
                    rs.qj = None
                else:

                    wait_entry = self.reorderbufferentry[self.registers.entry[instruction.vj] - 1].value

                    if wait_entry is not None:
                        rs.vj = wait_entry
                        rs.qj = None
                    else:

                        rs.vj = None
                        rs.qj = "#" + str(self.registers.entry[instruction.vj])

                        rs.ready = 0

                if self.registers.busy[instruction.vk] == "No":
                    rs.vk = "Regs[" + instruction.vk + "]"
                    rs.qk = None
                else:

                    wait_entry = self.reorderbufferentry[self.registers.entry[instruction.vk] - 1].value

                    if wait_entry is not None:
                        rs.vk = self.reorderbufferentry[
                            self.registers.entry[instruction.vk] - 1].value
                        rs.qk = None
                    else:

                        rs.vk = None
                        rs.qk = "#" + str(self.registers.entry[instruction.vk])

                        rs.ready = 0


                self.registers.entry[instruction.dest] = entry1.entry
                self.registers.busy[instruction.dest] = "Yes"


                return 1

            if op in {"fmul.d", "fdiv.d"} and self.rs_num["Mult"] > 0:
                entry1.time = "Issue"
                
                self.rs_num["Mult"] -= 1


                index = 5 if self.reservationstation[5].busy == "No" else 6


                rs = self.reservationstation[index]
                rs.entry = entry1.entry
                rs.busy = "Yes"
                rs.op = instruction.op
                rs.dest = "#" + str(entry1.entry)
                rs.need_time = EX_Cycles[instruction.op]


                rs.ready = 1


                if self.registers.busy[instruction.vj] == "No":
                    rs.vj = "Regs[" + instruction.vj + "]"
                    rs.qj = None
                else:

                    wait_entry = self.reorderbufferentry[self.registers.entry[instruction.vj] - 1].value

                    if wait_entry is not None:
                        rs.vj = self.reorderbufferentry[self.registers.entry[instruction.vj] - 1].value
                        rs.qj = None
                    else:

                        rs.vj = None
                        rs.qj = "#" + str(self.registers.entry[instruction.vj])

                        rs.ready = 0


                if self.registers.busy[instruction.vk] == "No":
                    rs.vk = "Regs[" + instruction.vk + "]"
                    rs.qk = None
                else:
                    wait_entry = self.reorderbufferentry[self.registers.entry[instruction.vk] - 1].value

                    if wait_entry is not None:
                        rs.vk = self.reorderbufferentry[
                            self.registers.entry[instruction.vk] - 1].value
                        rs.qk = None
                    else:

                        rs.vk = None
                        rs.qk = "#" + str(self.registers.entry[instruction.vk])

                        rs.ready = 0

                # 将对应目的寄存器的状态改为繁忙
                self.registers.entry[instruction.dest] = entry1.entry
                self.registers.busy[instruction.dest] = "Yes"


                return 1
        return 0
    '''
    Execute的说明
    只有reservation的条目ready=1，即源操作数都准备好了 数据冒险已经被解决了 才可以进入到execute 
    且execute不像之前的阶段 这个阶段的执行时间需要根据指令的类型决定，就是最初全局定义的：
    '''

    def Execute(self):
        global clock
        update = 0
        for rs in self.reservationstation:
            if rs.ready == 1 and rs.busy=="Yes":
                entry1 = rs.entry - 1
                if self.reorderbufferentry[entry1].time == "Issue":

                    update = 1
                    self.reorderbufferentry[entry1].time = "Execute"#有些执行周期需要很长可以合并

                rs.need_time -= 1

                if rs.need_time == 0:
                    self.reorderbufferentry[entry1].instruction.exec_time = clock
        return update

    '''
    write阶段的说明
    在这个阶段把相应的操作数的执行结果写回reorderbuffer的value属性中 
    并且看reservation 是否有指令在等待这个执行结果 有的话就要更新 看是否要更新为ready
    这里因为实验要求中给的指令没有具体的数 所以算术运算只能，比如加法用寄存器+寄存器表示最后加法的结果
    '''


    def Write(self):
        global clock
        for index, rs in enumerate(self.reservationstation):
            # if the instr finishes exe, then write result
            if rs.need_time == 0 and rs.ready == 1 and self.reorderbufferentry[rs.entry - 1].time == "Execute":

                # print(self.reorderbufferentry[rs.entry - 1].time)
                # self.reorderbufferentry[rs.entry - 1].time = "Write result"
                # self.reorderbufferentry[rs.entry - 1].instruction.write_time = clock
                # print(f"Write: {self.reorderbufferentry[rs.entry - 1].instruction.instruction}, current state: {self.reorderbufferentry[rs.entry - 1].time}")
                self.reorderbufferentry[rs.entry - 1].time = "Write result"
                # print(self.reorderbufferentry[rs.entry - 1].time)
                self.reorderbufferentry[rs.entry - 1].instruction.write_time = clock

                # use operands and op to compute result
                result = None
                if rs.op == "fld":
                    result = f"Mem[{rs.vj}+{rs.vk}]"
                elif rs.op == "fadd.d":
                    result = f"{rs.vj}+{rs.vk}"
                elif rs.op == "fsub.d":
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

                return 1
        return 0
    '''
    commit阶段的说明
    commit阶段就是清空reorderbuffer对应条目 释放reservation和register占用资源 并且注意要按顺序commit
    '''
    def Commit(self):
        global clock
        update = 0
        # release resources from committed reorder buffer
        for i in range(len(self.reorderbufferentry)):
            rf = self.reorderbufferentry[i]
            if rf.time == "Commit":
                rf.busy, rf.instruction, rf.time, rf.dest, rf.value = "No", None, None, None, None
                update = 1
        # for instr that wrote result, commit in order
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

                return 1
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
            output_file.write("reorderbuffer_entry: f0:")
            output_file.write(f"{entry1.entry['f0']}   ; f1:" if entry1.entry["f0"] is not None else "   ; f1:")
            for i in range(1, 10):
                output_file.write(
                    f"{entry1.entry['f' + str(i)]}   ; f{i + 1}:" if entry1.entry["f" + str(i)] is not None else "   ; f" + str(
                        i + 1) + ":")
            output_file.write(f"{entry1.entry['f10']}   ;\n" if entry1.entry["f10"] is not None else "   ;\n")

            busy = self.registers.busy
            output_file.write("Busy   : f0:")
            for i in range(0, 10):
                output_file.write(f"{busy['f' + str(i)]} ; f{i + 1}:")
            output_file.write(f"{busy['f10']} ;\n" if busy["f10"] is not None else ";\n")

            output_file.write("-----------------------------------------------------------------------------------\n\n")
    
    def write_results(self):
        with open(self.output_path, 'a',encoding='utf-8') as output_file:
            output_file.write(
                f"指令 \t , 发射指令的时钟周期\t, 执⾏指令的时钟周期 \t, 访问存储器的时钟周期\t, 写CDB的时钟周期\t\n")
            for instr in self.instruction_queue:
                output_file.write(
                    f"{instr.instruction} \t: {instr.issue_time} \t, {instr.exec_time} \t, {instr.write_time} \t, {instr.commit_time}\n")
    def run(self):
        global clock
        while True:
            # run Tomasulo until all instr have been committed
            if all(rf.time is None for rf in self.reorderbufferentry) and success():
                break

            update = 0
            update = update | self.Commit()
            update = update | self.Write()
            update = update | self.Execute()
            update = update | self.Issue()
            update = update | self.Decode()


            self.writeprocess()
            # tick the clock
            clock += 1
        # write the execution cycles of instructions to output_file
        self.write_results()


if __name__ == '__main__':
    Tomasulo = Tomasulo(Instruction_queue,"output_1.txt")

    # read input_file and initial the instruction queue in Tomasulo
    with open("1.txt", "r") as file:
        lines = [line.rstrip('\n') for line in file]
        for line in lines:
            push(Instruction_queue,line)
    Tomasulo.run()