#!/usr/bin/python

import os
import plistlib
import zipfile
import struct
import sys
from optparse import OptionParser
from crypto import aes_ctypes as AES
from util.lzss import decompress_lzss

devices = {"n82ap": "iPhone1,2",
           "n88ap": "iPhone2,1",
           "n90ap": "iPhone3,1",
           "n90bap": "iPhone3,2",
           "n92ap": "iPhone3,3",
           "n18ap": "iPod3,1",
           "n81ap": "iPod4,1",
           "k48ap": "iPad1,1",
           "n72ap": "iPod2,1",
           }

h=lambda x:x.replace(" ","").decode("hex")

#generated by idapy-IOFlashStorageControllerUserClient__externalMethod.py
#format: SecureRoot_file_offset, IOFCuc__externalMethod_file_offset, IOFCuc__externalMethod_size, IOMemoryDescriptor_withAddress_file_offset, IOMemoryDescriptor_withAddress_delta
IOFC_PATCH_INFO = {
    "iPhone2,1_5.0_9A334_Restore.ipsw":  [0x571913, 0x56d8f4, 0x118, 0x222f6c, 0xffc7366d],
    "iPhone3,1_5.0_9A334_Restore.ipsw":  [0x5f4913, 0x5f08f4, 0x118, 0x222f6c, 0xffbf066d],
    "iPhone3,1_6.0_10A403_Restore.ipsw": [0x4e98bd, 0x4e0984, 0xa8, 0x25cec4, 0xffd3c535],
    "iPhone3,2_6.0_10A403_Restore.ipsw": [0x4e98bd, 0x4e0984, 0xa8, 0x25cec4, 0xffd3c535],
    "iPhone3,3_6.0_10A403_Restore.ipsw": [0x79d8bd, 0x794984, 0xa8, 0x25cec4, 0xffa88535],

    #not supported by redsn0w yet
    "iPhone3,1_7.0_11A465_Restore.ipsw": [0x9278a3, 0x91eac8, 0xa4, 0x8f6b0, 0xff72bbdd],
}
#externalMethod.S => externalMethod.bin
IOFC_patch = h("F0 B5 96 B0 DF F8 9C B0 FB 44 04 46 D6 69 00 25 D2 F8 30 70 01 22 30 68 01 90 70 68 00 90 01 20 03 90 02 95 71 7A 11 F0 01 0F 1C BF 09 21 02 91 05 95 08 95 11 95 0F 95 0D 95 04 90 01 A8 06 90 68 46 0B 90 D6 E9 03 01 E3 6F D8 47 07 90 70 69 08 B9 2E 46 11 E0 B0 69 01 22 0D 90 70 69 B1 69 E3 6F D8 47 29 46 05 46 2A 68 D2 F8 98 20 90 47 06 46 31 68 89 6B 88 47 0C 90 A0 6F 02 AA 01 68 D1 F8 44 33 00 21 98 47 C7 F8 00 00 07 98 01 68 4C 69 A0 47 1E B1 30 46 A0 47 28 46 A0 47 00 20 16 B0 F0 BD")

def patch_IOFlashControllerUserClient_externalMethod(ipswname, kernel):
    if not IOFC_PATCH_INFO.has_key(ipswname):
        print "Unsupported IPSW for IOFlashControllerUserClient::externalMethod patch !"
        return kernel
    sr, externalMethod, fsz, _, delta = IOFC_PATCH_INFO[ipswname]

    assert kernel[sr:sr+10] == "SecureRoot"
    assert fsz >= (len(IOFC_patch)+4)

    patch = IOFC_patch + struct.pack("<L", delta)

    print "Added IOFlashControllerUserClient::externalMethod patch at file offset 0x%x" % externalMethod

    return kernel[:externalMethod] + patch + kernel[externalMethod+len(patch):]

#thx to 0x56
patchs_ios6 = {
    "IOAESAccelerator enable UID" : (h("B0 F5 FA 6F 00 F0 92 80"), h("B0 F5 FA 6F 00 20 00 20")),
    "_PE_i_can_has_debugger" : (h("80 B1 43 F2 BE 01 C0 F2"), h("01 20 70 47 BE 01 C0 F2")),

    #prevent panic with nand-disable-driver bootarg (was kprintf in ios5)
    "panic(AppleNANDFTL did not appear)" : (h("05 46 4D B9 58 48 78 44 0A F0 28 FE"), h("05 46 4D B9 58 48 78 44 00 20 00 20")),
    #nop _fmiPatchMetaFringe to get full spare metadata on PPN devices (70 47 => bx lr)
    "AppleIOPFMI::_fmiPatchMetaFringe": (h("F0 B5 03 AF 81 B0 1C 46  15 46 0E 46 B5 42"), h("70 47 03 AF 81 B0 1C 46  15 46 0E 46 B5 42"))
}

#https://github.com/comex/datautils0/blob/master/make_kernel_patchfile.c
patchs_ios5 = {
    "CSED" : (h("df f8 88 33 1d ee 90 0f a2 6a 1b 68"), h("df f8 88 33 1d ee 90 0f a2 6a 01 23")),
    "AMFI" : (h("D0 47 01 21 40 B1 13 35"), h("00 20 01 21 40 B1 13 35")),
    "_PE_i_can_has_debugger" : (h("38 B1 05 49 09 68 00 29"), h("01 20 70 47 09 68 00 29")),
    "task_for_pid_0" : (h("00 21 02 91 ba f1 00 0f 01 91 06 d1 02 a8"), h("00 21 02 91 ba f1 00 0f 01 91 06 e0 02 a8")),
    "IOAESAccelerator enable UID" : (h("67 D0 40 F6"), h("00 20 40 F6")),
    #not stritcly required, useful for testing
    "getxattr system": ("com.apple.system.\x00", "com.apple.aaaaaa.\x00"),
    "IOAES gid": (h("40 46 D4 F8 54 43 A0 47"), h("40 46 D4 F8 43 A0 00 20")),
    #HAX to fit into the 40 char boot-args (redsn0w 0.9.10)
    "nand-disable-driver": ("nand-disable-driver\x00", "nand-disable\x00\x00\x00\x00\x00\x00\x00\x00"),
    #nop _fmiPatchMetaFringe to get full spare metadata on PPN devices (70 47 => bx lr)
    "AppleIOPFMI::_fmiPatchMetaFringe": (h("F0 B5 03 AF 81 B0 1C 46  15 46 0E 46 B5 42"), h("70 47 03 AF 81 B0 1C 46  15 46 0E 46 B5 42"))
}

patchs_ios4 = {
    "NAND_epoch" : ("\x90\x47\x83\x45", "\x90\x47\x00\x20"),
    "CSED" : ("\x00\x00\x00\x00\x01\x00\x00\x00\x80\x00\x00\x00\x00\x00\x00\x00", "\x01\x00\x00\x00\x01\x00\x00\x00\x80\x00\x00\x00\x00\x00\x00\x00"),
    "AMFI" : ("\x01\xD1\x01\x30\x04\xE0\x02\xDB", "\x00\x20\x01\x30\x04\xE0\x02\xDB"),
    "_PE_i_can_has_debugger" : (h("48 B1 06 4A 13 68 13 B9"), h("01 20 70 47 13 68 13 B9")),
    "IOAESAccelerator enable UID" : ("\x56\xD0\x40\xF6", "\x00\x00\x40\xF6"),
    "getxattr system": ("com.apple.system.\x00", "com.apple.aaaaaa.\x00"),
}

patchs_armv6 = {
    "NAND_epoch" : (h("00 00 5B E1 0E 00 00 0A"), h("00 00 5B E1 0E 00 00 EA")),
    "CSED" : (h("00 00 00 00 01 00 00 00 80 00 00 00 00 00 00 00"), h("01 00 00 00 01 00 00 00 80 00 00 00 00 00 00 00")),
    "AMFI" : (h("00 00 00 0A 00 40 A0 E3 04 00 A0 E1 90 80 BD E8"), h("00 00 00 0A 00 40 A0 E3 01 00 A0 E3 90 80 BD E8")),
    "_PE_i_can_has_debugger" : (h("00 28 0B D0 07 4A 13 68 00 2B 02 D1 03 60 10 68"), h("01 20 70 47 07 4A 13 68 00 2B 02 D1 03 60 10 68")),
    "IOAESAccelerator enable UID" : (h("5D D0 36 4B 9A 42"), h("00 20 36 4B 9A 42")),
    "IOAES gid": (h("FA 23 9B 00 9A 42 05 D1"), h("00 20 00 20 9A 42 05 D1")),
    "nand-disable-driver": ("nand-disable-driver\x00", "nand-disable\x00\x00\x00\x00\x00\x00\x00\x00"),
}
patchs_ios4_fixnand = {
    "Please reboot => jump to prepare signature": (h("B0 47 DF F8 E8 04 F3 E1"), h("B0 47 DF F8 E8 04 1D E0")),
    "prepare signature => jump to write signature": (h("10 43 18 60 DF F8 AC 04"), h("10 43 18 60 05 E1 00 20")),
    "check write ok => infinite loop" : (h("A3 48 B0 47 01 24"), h("A3 48 B0 47 FE E7"))
}

#grab keys from redsn0w Keys.plist
class IPSWkeys(object):
    def __init__(self, manifest):
        self.keys = {}
        buildi = manifest["BuildIdentities"][0]
        dc = buildi["Info"]["DeviceClass"]
        build = "%s_%s_%s" % (devices.get(dc,dc), manifest["ProductVersion"], manifest["ProductBuildVersion"])
        print "build: " + str(build)
        try:
            rs = plistlib.readPlist("Keys.plist")
        except:
            raise Exception("Get Keys.plist from redsn0w and place it in the current directory")
        for k in rs["Keys"]:
            if k["Build"] == build:
                self.keys = k
                break

    def getKeyIV(self, filename):
        if not self.keys.has_key(filename):
            return None, None
        k = self.keys[filename]
        print k.get("Key",""), k.get("IV","")
        return k.get("Key",""), k.get("IV","")
    
def decryptImg3(blob, key, iv):
    assert blob[:4] == "3gmI", "Img3 magic tag"
    data = ""
    for i in xrange(20, len(blob)):
        tag = blob[i:i+4]
        size, real_size = struct.unpack("<LL", blob[i+4:i+12])
        if tag[::-1] == "DATA":
            assert size >= real_size, "Img3 length check"
            data = blob[i+12:i+size]
            break
        i += size
    if key == "": return data[:real_size]
    return AES.new(key, AES.MODE_CBC, iv).decrypt(data)[:real_size]

def main():
    kernel_path = '/Applications/Sliver.app/Contents/Resources/Master/iphone4gsm/kernelcache'
    kernel_img3_file = open(kernel_path, 'rb')
    kernel_img3 = kernel_img3_file.read()
    print "type(kernel_img3) = " + str(type(kernel_img3))
    print "img3File.ident = " + kernel_img3[16:16 + 4][::-1]
    kernel_lzss = decryptImg3(kernel_img3, "", "")  # Slivers kernelcaches are not encrypted
    kernel_img3_file.close()
    kernel = decompress_lzss(kernel_lzss)

    patchfail = False
    device_to_patches = {
        "patchs_ios6": patchs_ios6,
        "patchs_ios5": patchs_ios5,
        "patchs_ios4": patchs_ios4,
        "patchs_armv6": patchs_armv6
    }
    device_to_patched_kernel = {}
    matching_devices = []
    for device in device_to_patches:
        print "Trying to patch for device '" + device + "' ..."
        patchfail = False
        patchs = device_to_patches[device]
        device_to_patched_kernel[device] = kernel
        for p in patchs:
            print "Doing %s patch" % p
            s, r = patchs[p]
            c = kernel.count(s)
            if c != 1:
                print "=> FAIL, count=%d, do not boot that kernel it wont work" % c
                patchfail = True
                break
            else:
                device_to_patched_kernel[device] = device_to_patched_kernel[device].replace(s, r)
                
        if not patchfail:
            matching_devices.append(device)
    print "Possible Matching OS (hopefully this is exactly one ...): " + str(matching_devices)
    assert len(matching_devices) == 1, "no or more than one device matches; do not know what to choose ..."
    assert matching_devices[0] == "patchs_ios6"

    kernel_patched = device_to_patched_kernel[matching_devices[0]]
    # kernel_patched = patch_IOFlashControllerUserClient_externalMethod(ipswname, kernel)  # TODO: do not know the ipswname yet (it should be "iPhone3,1_6.0_10A403_Restore.ipsw")
    kernel_patched_path = kernel_path + ".patched"
    print "Saving to '" +  kernel_patched_path + "'"
    f = open(kernel_patched_path, "wb")
    f.write(kernel_patched)
    f.close()

        
    

def main_previous(ipswname, options):
    ipsw = zipfile.ZipFile(ipswname)
    ipswname = os.path.basename(ipswname)
    manifest = plistlib.readPlistFromString(ipsw.read("BuildManifest.plist"))
    kernelname = manifest["BuildIdentities"][0]["Manifest"]["KernelCache"]["Info"]["Path"]
    print "kernelname: " + str(kernelname)
    devclass = manifest["BuildIdentities"][0]["Info"]["DeviceClass"]
    kernel = ipsw.read(kernelname)
    keys = IPSWkeys(manifest)
    
    key,iv = keys.getKeyIV(kernelname)
    
    if key == None:
        print "No keys found for kernel"
        return -1
    
    print "Decrypting %s" % kernelname
    kernel = decryptImg3(kernel, key.decode("hex"), iv.decode("hex"))

    assert kernel.startswith("complzss"), "Decrypted kernelcache does not start with \"complzss\" => bad key/iv ?"
    
    print "Unpacking ..."
    kernel = decompress_lzss(kernel)
    assert kernel.startswith("\xCE\xFA\xED\xFE"), "Decompressed kernelcache does not start with 0xFEEDFACE"
    
    patchs = patchs_ios5
    if devclass in ["n82ap", "n72ap"]:
        print "Using ARMv6 kernel patches"
        patchs = patchs_armv6
    elif manifest["ProductVersion"].startswith("4."):
        print "Using iOS 4 kernel patches"
        patchs = patchs_ios4
    elif manifest["ProductVersion"].startswith("6."):
        print "Using iOS 6 kernel patches"
        patchs = patchs_ios6

    if options.fixnand:
        if patchs != patchs_ios4:
            print "FAIL : use --fixnand with iOS 4.x IPSW"
            return
        patchs.update(patchs_ios4_fixnand)
        kernelname = "fix_nand_" + kernelname
        print "WARNING : only use this kernel to fix NAND epoch brick"
    
    patchfail = False
    for p in patchs:
        print "Doing %s patch" % p
        s, r = patchs[p]
        c = kernel.count(s)
        if c != 1:
            print "=> FAIL, count=%d, do not boot that kernel it wont work" % c
            patchfail = True
        else:
            kernel = kernel.replace(s,r)

    if patchfail:
        return -1
    if manifest["ProductVersion"] >= "5.0":
        kernel = patch_IOFlashControllerUserClient_externalMethod(ipswname, kernel)

    ipswname = ipswname.replace("_Restore.ipsw", "")
    outkernel = "data/boot/kernel_%s.patched" % ipswname
    f = open(outkernel, "wb")
    f.write(kernel)
    f.close()
    print "Patched kernel written to %s" % outkernel
    
    ramdiskname = manifest["BuildIdentities"][0]["Manifest"]["RestoreRamDisk"]["Info"]["Path"]
    key,iv = keys.getKeyIV("Ramdisk")
    ramdisk = ipsw.read(ramdiskname)

    print "Decrypting %s" % ramdiskname
    ramdisk = decryptImg3(ramdisk, key.decode("hex"), iv.decode("hex"))

    assert ramdisk[0x400:0x402] == "H+", "H+ magic not found in decrypted ramdisk => bad key/iv ?"

    customramdisk = "data/boot/ramdisk_%s.dmg" % ipswname
    
    if os.path.exists(customramdisk):
        print "Ramdisk %s already exists" % customramdisk
        return

    f = open(customramdisk, "wb")
    f.write(ramdisk)
    f.close()
    print "Decrypted ramdisk written to %s" % customramdisk

if __name__ == "__main__":
    exit(main())
    parser = OptionParser(usage="%prog [options] IPSW")
    parser.add_option("-f", "--fixnand",
                      action="store_true", dest="fixnand", default=False,
                      help="Apply NAND epoch fix kernel patches")
    
    (options, args) = parser.parse_args()
    if len(args) < 1:
        parser.print_help()
    else:
        exit(main(args[0], options))
