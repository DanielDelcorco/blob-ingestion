
class StreamWrapper:
    def __init__(self, downloader, encoding='cp1252'):
        self.iterator = downloader.chunks()
        self.buffer = ''
        self.encoding = encoding
        self.closed = False

    def read(self, size=-1):
        while not self.closed and (size < 0 or len(self.buffer) < size):
            try:
                self.buffer += next(self.iterator).decode(self.encoding)
            except StopIteration:
                break
        
        if size < 0:
            result, self.buffer = self.buffer, ''
        else:
            result, self.buffer = self.buffer[:size], self.buffer[size:]

        return result

    def close(self):
        self.closed = True