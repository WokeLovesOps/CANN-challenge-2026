// 仅用于真机错误定位的LD_PRELOAD辅助库，不得用于性能测试或提交算子。
// 在工作区释放前回读分配内容，不修改设备数据；需显式设置BMM_DUMP_DIR。
#include <cstdio>
#include <cstdlib>
#include <dlfcn.h>
#include <map>
#include <mutex>
#include <vector>

struct Allocation {
    size_t bytes;
    unsigned index;
};
static std::map<void*, Allocation>& Allocations()
{
    static std::map<void*, Allocation> allocations;
    return allocations;
}
static std::mutex& AllocationMutex()
{
    static std::mutex mutex;
    return mutex;
}
extern "C" int aclrtMalloc(void** address, size_t bytes, int policy)
{
    using Malloc = int (*)(void**, size_t, int);
    static auto realMalloc = reinterpret_cast<Malloc>(dlsym(RTLD_NEXT, "aclrtMalloc"));
    if (!realMalloc) return -1;
    int status = realMalloc(address, bytes, policy);
    if (status == 0 && std::getenv("BMM_DUMP_DIR")) {
        std::lock_guard<std::mutex> lock(AllocationMutex());
        static unsigned sequence = 0;
        Allocations()[*address] = {bytes, sequence++};
    }
    return status;
}
extern "C" int aclrtFree(void* address)
{
    using Free = int (*)(void*);
    using Copy = int (*)(void*, size_t, const void*, size_t, int);
    static auto realFree = reinterpret_cast<Free>(dlsym(RTLD_NEXT, "aclrtFree"));
    static auto copy = reinterpret_cast<Copy>(dlsym(RTLD_NEXT, "aclrtMemcpy"));
    if (!realFree) return -1;
    const char* directory = std::getenv("BMM_DUMP_DIR");
    if (directory && copy) {
        std::lock_guard<std::mutex> lock(AllocationMutex());
        auto it = Allocations().find(address);
        if (it != Allocations().end()) {
            auto allocation = it->second;
            // 排除系统通信工作区，保留相似度和归约临时区；只读回最多8MiB。
            if (allocation.bytes <= 8 * 1024 * 1024) {
                std::vector<unsigned char> data(allocation.bytes);
                int status = copy(data.data(), data.size(), address, data.size(), 2);
                char path[1024];
                std::snprintf(path, sizeof(path), "%s/allocation-%u-%zu.bin",
                    directory, allocation.index, allocation.bytes);
                if (status == 0) {
                    if (FILE* file = std::fopen(path, "wb")) {
                        std::fwrite(data.data(), 1, data.size(), file);
                        std::fclose(file);
                    }
                }
                std::fprintf(stderr, "工作区回读 index=%u bytes=%zu status=%d\n",
                    allocation.index, allocation.bytes, status);
            }
            Allocations().erase(it);
        }
    }
    return realFree(address);
}
