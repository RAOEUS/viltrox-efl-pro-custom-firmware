import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.lang.*;
public class FillGaps extends GhidraScript {
    public void run() throws Exception {
        Listing l = currentProgram.getListing();
        Register tm = currentProgram.getProgramContext().getRegister("TMode");
        for (int pass = 0; pass < 4; pass++) {
            int added = 0;
            long a = 0x08020594L; // after vector table
            while (a < 0x0802D9C0L) {
                Address ad = toAddr(a);
                CodeUnit cu = l.getCodeUnitContaining(ad);
                if (cu instanceof Data && !((Data)cu).isDefined()) {
                    // undefined byte: skip 0x00/0xff padding, else try code
                    int b = currentProgram.getMemory().getByte(ad) & 0xff;
                    int b1 = currentProgram.getMemory().getByte(ad.add(1)) & 0xff;
                    if ((b == 0 && b1 == 0) || (b == 0xff && b1 == 0xff)) { a += 2; continue; }
                    try {
                        currentProgram.getProgramContext().setValue(tm, ad, ad, java.math.BigInteger.ONE);
                        disassemble(ad);
                        if (getInstructionAt(ad) != null && createFunction(ad, null) != null) added++;
                    } catch (Exception e) {}
                    a += 2;
                } else a = cu.getMaxAddress().getOffset() + 1;
            }
            analyzeChanges(currentProgram);
            println("pass " + pass + " added " + added + " functions=" + currentProgram.getFunctionManager().getFunctionCount());
            if (added == 0) break;
        }
    }
}
